"""
LearnNest Case Study: Integrating MongoDB into the Student Record System
=========================================================================
10Alytics | Specialization: Databases | Business Focus: Education

LearnNest already keeps its core records in PostgreSQL (schema: public):

    students      (student_id PK, name, age, graduated)
    courses       (course_id PK, name, course_unit)
    teachers      (teacher_id PK, name, is_admin)
    final_grades  (scid PK, student_id FK, teacher_id FK, course_id FK, score)

This walkthrough adds MongoDB ALONGSIDE PostgreSQL to hold the flexible,
fast-growing data that doesn't fit those fixed tables:

    project_submissions  - one per student per course; rubric differs by course
    mentor_feedback      - threaded comments from teachers on a submission
    activity_logs        - high-volume learner events

Every MongoDB document carries the same student_id / course_id / teacher_id
values used in PostgreSQL, so the two can be joined.

Workflow
    STEP 1  Audit the SQL database
    STEP 2  Set up MongoDB
    STEP 3  Load & manage data (CRUD)
    STEP 4  Query & optimise (aggregation + indexes)
    STEP 5  Integrate with SQL
    STEP 6  Bringing it all together: the student performance report

Requirements
    pip install pymongo psycopg2-binary pandas
    PostgreSQL with the four tables above, and a MongoDB server:
        docker run -d -p 27017:27017 --name mongo mongo:7

Run
    python learnnest_mongodb_walkthrough.py --seed   # first time: creates + fills the SQL tables
    python learnnest_mongodb_walkthrough.py          # later runs: uses the data already in PostgreSQL

    Connection strings come from environment variables:
        PG_DSN="postgresql://postgres:password@localhost:5432/learnnest"
        MONGO_URI="mongodb://localhost:27017"
"""

import os
import random
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import psycopg2
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import CollectionInvalid, DuplicateKeyError

PG_DSN = os.getenv("PG_DSN", "postgresql://admin_officer:pmNr7kzMrl0nDZPojRR5nltTahlZoZra@dpg-dan64ggae00c73dl2tv0-a.virginia-postgres.render.com/learnest_db")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = "learnnest"

# final_grades.score is numeric(3,2), so it can only hold 0.00 - 9.99.
# We treat it as a grade point on a 5.00 scale; change this if yours differs.
SCORE_SCALE = 5.0


def banner(title):
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def sql_df(conn, query, params=None):
    """Run a SELECT on PostgreSQL and return a pandas DataFrame."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        cols = [c[0] for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


# =============================================================================
# STEP 1: AUDIT THE SQL DATABASE
# Goal: understand what's already in PostgreSQL and what it can't hold.
# =============================================================================

def get_sql_connection():
    return psycopg2.connect(PG_DSN)


def seed_sql(conn):
    """Creates the schema from the ERD and fills it with sample data.
    WARNING: wipes these four tables. Only run with --seed on a practice DB."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id  VARCHAR(6) PRIMARY KEY,
                name        VARCHAR(60),
                age         INTEGER,
                graduated   BOOLEAN
            );
            CREATE TABLE IF NOT EXISTS courses (
                course_id   VARCHAR(6) PRIMARY KEY,
                name        VARCHAR(30),
                course_unit INTEGER
            );
            CREATE TABLE IF NOT EXISTS teachers (
                teacher_id  VARCHAR(6) PRIMARY KEY,
                name        VARCHAR(60),
                is_admin    BOOLEAN
            );
            CREATE TABLE IF NOT EXISTS final_grades (
                scid        SERIAL PRIMARY KEY,
                student_id  VARCHAR(6) REFERENCES students(student_id),
                teacher_id  VARCHAR(6) REFERENCES teachers(teacher_id),
                score       NUMERIC(3,2),
                course_id   VARCHAR(6) REFERENCES courses(course_id)
            );
            TRUNCATE final_grades, students, courses, teachers RESTART IDENTITY CASCADE;
        """)
        cur.executemany("INSERT INTO students VALUES (%s,%s,%s,%s)", [
            ("STU001", "Tega", 24, False),
            ("STU002", "Pruva", 29, False),
            ("STU003", "Ceaser", 22, False),
            ("STU004", "Gbenga", 31, True),
            ("STU005", "Daniel", 26, False),
            ("STU006", "Emeka", 27, False),
        ])
        cur.executemany("INSERT INTO courses VALUES (%s,%s,%s)", [
            ("PY101", "Python Basics",  3),
            ("SQL201", "SQL Essentials", 2),
            ("DE301", "Data Pipelines", 4),
        ])
        cur.executemany("INSERT INTO teachers VALUES (%s,%s,%s)", [
            ("TCH001", "Sadique", True),
            ("TCH002", "Ngozi Adeyemi", False),
            ("TCH003", "Bola Ahmed",   False),
        ])
        cur.executemany(
            "INSERT INTO final_grades (student_id, teacher_id, score, course_id) "
            "VALUES (%s,%s,%s,%s)", [
                ("STU001", "TCH001", 4.50, "PY101"),
                ("STU001", "TCH002", 3.80, "SQL201"),
                ("STU002", "TCH001", 4.20, "PY101"),
                ("STU002", "TCH003", 4.70, "DE301"),
                ("STU003", "TCH002", 3.10, "SQL201"),
                ("STU003", "TCH001", 2.90, "PY101"),
                ("STU004", "TCH003", 4.90, "DE301"),
                ("STU004", "TCH002", 4.40, "SQL201"),
                ("STU005", "TCH003", 3.60, "DE301"),
                ("STU006", "TCH001", 2.40, "PY101"),
                ("STU006", "TCH003", 3.00, "DE301"),
            ])
    conn.commit()
    print("Seeded PostgreSQL with sample students, courses, teachers and final_grades.")


def audit_sql(conn):
    banner("STEP 1: Audit the SQL database")

    tables = sql_df(conn, """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)["table_name"].tolist()

    print("Tables in schema 'public':")
    for t in tables:
        cols = sql_df(conn, """
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (t,))
        count = sql_df(conn, f'SELECT COUNT(*) AS n FROM "{t}"')["n"][0]
        col_list = ", ".join(cols["column_name"])
        print(f"  - {t:<14} {count:>3} rows | {col_list}")

    stats = sql_df(conn, """
        SELECT COUNT(DISTINCT student_id) AS students_graded,
               COUNT(*)                   AS grade_rows,
               ROUND(AVG(score), 2)       AS avg_score
        FROM final_grades
    """).iloc[0]
    print(f"\nfinal_grades: {stats.grade_rows} grades for {stats.students_graded} students, "
          f"average {stats.avg_score} / {SCORE_SCALE:.2f}")

    print("\nWhat final_grades can't capture:")
    print("  - Only ONE number per course: no rubric breakdown, no project artifacts")
    print("  - No place for teacher feedback threads or resubmissions")
    print("  - Learner activity (logins, lesson views) would flood a relational table")
    print("\nDecision:")
    print("  KEEP in PostgreSQL -> students, courses, teachers, final_grades")
    print("  ADD in MongoDB     -> project_submissions, mentor_feedback, activity_logs")


# =============================================================================
# STEP 2: SET UP MONGODB
# Goal: connect, create the database and collections, add light validation.
# =============================================================================

def get_mongo_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")          # fail fast if the server isn't up
    return client, client[MONGO_DB]


SUBMISSION_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["student_id", "course_id", "teacher_id", "project", "submitted_at", "rubric"],
        "properties": {
            # Same format as the VARCHAR(6) keys in PostgreSQL
            "student_id": {"bsonType": "string", "maxLength": 6},
            "course_id":  {"bsonType": "string", "maxLength": 6},
            "teacher_id": {"bsonType": "string", "maxLength": 6},
            "project":    {"bsonType": "string"},
            "status":     {"enum": ["submitted", "graded", "resubmit"]},
            "rubric": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": ["criterion", "score", "max"],
                    "properties": {
                        "criterion": {"bsonType": "string"},
                        "score":     {"bsonType": ["int", "double"], "minimum": 0},
                        "max":       {"bsonType": ["int", "double"], "minimum": 1},
                    },
                },
            },
        },
    }
}


def setup_mongo(db):
    banner("STEP 2: Set up MongoDB")
    # Start clean so the walkthrough is repeatable
    for name in ["project_submissions", "mentor_feedback", "activity_logs"]:
        db.drop_collection(name)

    # Flexible does NOT mean schemaless: validate the fields every document needs
    try:
        db.create_collection("project_submissions", validator=SUBMISSION_SCHEMA)
    except CollectionInvalid:
        pass
    db.create_collection("mentor_feedback")
    db.create_collection("activity_logs")

    print(f"Connected to {MONGO_URI} -> database '{MONGO_DB}'")
    print("Collections:", ", ".join(sorted(db.list_collection_names())))


# =============================================================================
# STEP 3: LOAD & MANAGE DATA (CRUD)
# Goal: Create, Read, Update and Delete documents with PyMongo.
# =============================================================================

def now_minus(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


# Each course grades its project differently. In SQL this would mean a new
# column per criterion; in MongoDB it's just a different array.
RUBRICS = {
    "PY101":  ("Student Record System", [("Data Types", 20), ("Functions", 30), ("Output Formatting", 50)]),
    "SQL201": ("Sales Analysis Queries", [("Joins", 30), ("Aggregations", 30), ("Query Performance", 40)]),
    "DE301":  ("Kafka Streaming Pipeline", [("Pipeline Design", 30), ("Reliability", 40), ("Documentation", 30)]),
}
DEFAULT_RUBRIC = ("Capstone Project", [("Technical Quality", 50), ("Presentation", 50)])


def build_submission(row, days_ago):
    """Turns one final_grades row into a MongoDB project submission.
    Scores are generated (repeatably) for the sake of the exercise."""
    project, criteria = RUBRICS.get(row.course_id, DEFAULT_RUBRIC)
    rng = random.Random(f"{row.student_id}-{row.course_id}")
    # Stronger SQL scores -> stronger project scores, plus some noise
    level = float(row.score) / SCORE_SCALE
    rubric = [{"criterion": c, "max": m,
               "score": max(0, min(m, round(m * (level + rng.uniform(-0.12, 0.08)))))}
              for c, m in criteria]
    return {
        "student_id": row.student_id,
        "course_id": row.course_id,
        "teacher_id": row.teacher_id,
        "project": project,
        "submitted_at": now_minus(days_ago),
        "status": "graded",
        "rubric": rubric,
        "total_score": sum(r["score"] for r in rubric),
    }


def crud_operations(db, conn):
    banner("STEP 3: Load & manage data (CRUD)")
    subs = db.project_submissions

    # ---- CREATE (one document, written out in full) ------------------------
    # Every document's student/course/teacher IDs come from PostgreSQL
    grades = sql_df(conn, "SELECT student_id, course_id, teacher_id, score "
                          "FROM final_grades ORDER BY scid")
    first = grades.iloc[0]
    one = {
        "student_id": first.student_id,
        "course_id": first.course_id,
        "teacher_id": first.teacher_id,
        "project": RUBRICS.get(first.course_id, DEFAULT_RUBRIC)[0],
        "submitted_at": now_minus(20),
        "status": "submitted",
        "artifacts": {"repo": "github.com/learnnest/student-record-system",
                      "files": ["records.py", "README.md"]},
        "rubric": [{"criterion": c, "score": 0, "max": m}
                   for c, m in RUBRICS.get(first.course_id, DEFAULT_RUBRIC)[1]],
    }
    result = subs.insert_one(one)
    print(f"[CREATE] insert_one  -> {first.student_id} / {first.course_id} (_id {result.inserted_id})")

    # ---- CREATE (many documents) -------------------------------------------
    docs = [build_submission(r, days_ago=18 - i % 10)
            for i, r in enumerate(grades.iloc[1:].itertuples())]
    # Artifacts differ by course: a free-form sub-document, no schema change
    for d in docs:
        if d["course_id"] == "DE301":
            d["artifacts"] = {"repo": f"github.com/{d['student_id'].lower()}/kafka",
                              "dag": "stream_dag.py", "metrics": {"throughput_msgs_s": 1200}}
        elif d["course_id"] == "SQL201":
            d["artifacts"] = {"queries_file": "analysis.sql"}
    subs.insert_many(docs)
    print(f"[CREATE] insert_many -> {len(docs)} more project submissions")

    # Mentor feedback REFERENCES a submission (threads can grow without limit)
    feedback = []
    for d in subs.find({"status": "graded"}).limit(4):
        feedback.append({
            "submission_id": d["_id"], "student_id": d["student_id"],
            "teacher_id": d["teacher_id"], "created_at": now_minus(12),
            "comments": [{"by": d["teacher_id"], "msg": "Solid work. See rubric notes.",
                          "at": now_minus(12)}],
        })
    db.mentor_feedback.insert_many(feedback)
    print(f"[CREATE] inserted {len(feedback)} mentor feedback threads")

    # Activity logs: many small, append-only events
    events = []
    for i, sid in enumerate(sorted(grades["student_id"].unique())):
        for d in range(0, 14, 1 + i % 3):   # students study at different rates
            events.append({"student_id": sid, "event": "lesson_view", "ts": now_minus(d)})
        events.append({"student_id": sid, "event": "login", "ts": now_minus(1)})
    db.activity_logs.insert_many(events)
    print(f"[CREATE] inserted {len(events)} activity log events")

    # ---- READ --------------------------------------------------------------
    print("\n[READ] DE301 submissions scoring 80+:")
    for doc in subs.find({"course_id": "DE301", "total_score": {"$gte": 80}},
                         {"_id": 0, "student_id": 1, "project": 1, "total_score": 1}):
        print("   ", doc)

    print("[READ] Submissions with pipeline metrics (nested field query):")
    for doc in subs.find({"artifacts.metrics": {"$exists": True}},
                         {"_id": 0, "student_id": 1, "artifacts.metrics": 1}).limit(3):
        print("   ", doc)

    # ---- UPDATE ------------------------------------------------------------
    # Grade the submission we inserted with insert_one
    project, criteria = RUBRICS.get(first.course_id, DEFAULT_RUBRIC)
    graded = build_submission(first, days_ago=20)
    res = subs.update_one(
        {"_id": result.inserted_id},
        {"$set": {"rubric": graded["rubric"], "total_score": graded["total_score"],
                  "status": "graded", "graded_at": datetime.now(timezone.utc)}})
    print(f"\n[UPDATE] graded {first.student_id}'s {first.course_id} project "
          f"-> {graded['total_score']}/100 (modified {res.modified_count})")

    # Append a reply to a feedback thread with $push
    thread = db.mentor_feedback.find_one()
    db.mentor_feedback.update_one(
        {"_id": thread["_id"]},
        {"$push": {"comments": {"by": thread["student_id"],
                                "msg": "Thanks! Fixed and pushed v2.", "at": now_minus(0)}}})
    print(f"[UPDATE] {thread['student_id']} replied to their feedback thread ($push)")

    # ---- DELETE ------------------------------------------------------------
    # Retention rule: drop activity logs older than 10 days
    res = db.activity_logs.delete_many({"ts": {"$lt": now_minus(10)}})
    print(f"[DELETE] removed {res.deleted_count} activity events older than 10 days")


# =============================================================================
# STEP 4: QUERY & OPTIMISE (AGGREGATION + INDEXES)
# Goal: compute insights in the database and keep common queries fast.
# =============================================================================

def query_and_optimise(db):
    banner("STEP 4: Query & optimise")
    subs = db.project_submissions

    # ---- Indexes on the fields we filter / sort by most --------------------
    subs.create_index([("student_id", ASCENDING)])
    subs.create_index([("course_id", ASCENDING), ("total_score", DESCENDING)])
    subs.create_index([("student_id", ASCENDING), ("course_id", ASCENDING)], unique=True)
    db.mentor_feedback.create_index("submission_id")
    db.activity_logs.create_index([("student_id", ASCENDING), ("ts", DESCENDING)])
    print("Indexes on project_submissions:", list(subs.index_information().keys()))

    # Unique (student_id, course_id): one project per student per course
    any_doc = subs.find_one()
    try:
        subs.insert_one({k: any_doc[k] for k in
                         ["student_id", "course_id", "teacher_id", "project", "rubric"]}
                        | {"submitted_at": now_minus(0)})
    except DuplicateKeyError:
        print("Duplicate submission blocked by the unique index.")

    # Prove the index is used: look for IXSCAN in the query plan
    plan = subs.find({"course_id": "DE301"}).sort("total_score", -1).explain()
    print("Query plan uses an index (IXSCAN):",
          "IXSCAN" in str(plan.get("queryPlanner", {}).get("winningPlan", {})))

    # ---- Aggregation 1: project performance per course ---------------------
    print("\nProject score by course (graded only):")
    pipeline = [
        {"$match": {"status": "graded"}},
        {"$group": {"_id": "$course_id",
                    "avg_score": {"$avg": "$total_score"},
                    "top_score": {"$max": "$total_score"},
                    "students":  {"$sum": 1}}},
        {"$sort": {"avg_score": -1}},
    ]
    for row in subs.aggregate(pipeline):
        print(f"   {row['_id']:<7} avg {row['avg_score']:>5.1f} | "
              f"top {row['top_score']:>3} | {row['students']} students")

    # ---- Aggregation 2: weakest rubric criterion per course ($unwind) ------
    print("\nWeakest rubric criterion per course (% of max):")
    pipeline = [
        {"$match": {"status": "graded"}},
        {"$unwind": "$rubric"},
        {"$group": {"_id": {"course": "$course_id", "criterion": "$rubric.criterion"},
                    "pct": {"$avg": {"$divide": ["$rubric.score", "$rubric.max"]}}}},
        {"$sort": {"pct": 1}},
        {"$group": {"_id": "$_id.course",
                    "weakest": {"$first": "$_id.criterion"},
                    "pct": {"$first": "$pct"}}},
        {"$sort": {"_id": 1}},
    ]
    for row in subs.aggregate(pipeline):
        print(f"   {row['_id']:<7} {row['weakest']:<20} {row['pct'] * 100:.0f}%")

    # ---- Aggregation 3: engagement from activity logs ----------------------
    print("\nEngagement (events in the last 10 days):")
    pipeline = [
        {"$group": {"_id": "$student_id", "events": {"$sum": 1}}},
        {"$sort": {"events": -1, "_id": 1}},
    ]
    for row in db.activity_logs.aggregate(pipeline):
        print(f"   {row['_id']}: {row['events']} events")


# =============================================================================
# STEP 5: INTEGRATE WITH SQL
# Goal: join MongoDB documents to PostgreSQL records on the shared IDs.
# =============================================================================

def integrate_with_sql(db, conn):
    banner("STEP 5: Integrate with SQL")

    # From PostgreSQL: who, which course, taught by whom, official score
    sql = sql_df(conn, """
        SELECT fg.scid,
               s.student_id, s.name AS student, s.graduated,
               c.course_id,  c.name AS course,  c.course_unit,
               t.teacher_id, t.name AS teacher,
               fg.score
        FROM final_grades fg
        JOIN students s ON s.student_id = fg.student_id
        JOIN courses  c ON c.course_id  = fg.course_id
        JOIN teachers t ON t.teacher_id = fg.teacher_id
    """)
    sql["score"] = sql["score"].astype(float)
    print(f"PostgreSQL rows (final_grades joined): {len(sql)}")

    # From MongoDB: project scores + number of feedback comments per submission
    feedback_counts = {r["_id"]: r["n"] for r in db.mentor_feedback.aggregate([
        {"$group": {"_id": "$submission_id", "n": {"$sum": {"$size": "$comments"}}}}])}
    mongo_rows = []
    for d in db.project_submissions.find(
            {}, {"student_id": 1, "course_id": 1, "project": 1, "status": 1, "total_score": 1}):
        mongo_rows.append({"student_id": d["student_id"], "course_id": d["course_id"],
                           "project": d["project"], "status": d["status"],
                           "project_score": d.get("total_score"),
                           "feedback_comments": feedback_counts.get(d["_id"], 0)})
    mongo = pd.DataFrame(mongo_rows)
    print(f"MongoDB rows (project_submissions): {len(mongo)}")

    # Data-quality check: every MongoDB key must exist in PostgreSQL
    orphans = set(zip(mongo.student_id, mongo.course_id)) - set(zip(sql.student_id, sql.course_id))
    print("Orphan (student_id, course_id) pairs in MongoDB:", orphans or "none")

    return sql.merge(mongo, on=["student_id", "course_id"], how="left")


# =============================================================================
# STEP 6: BRINGING IT ALL TOGETHER - STUDENT PERFORMANCE REPORT
# Goal: one clean report students and staff can trust.
# =============================================================================

def build_report(merged):
    banner("STEP 6: Student performance report")

    def band(pct):
        if pd.isna(pct):
            return "Pending"
        if pct >= 80:
            return "Distinction"
        if pct >= 65:
            return "Merit"
        if pct >= 50:
            return "Pass"
        return "Needs Support"

    merged["score_pct"] = merged["score"] / SCORE_SCALE * 100
    # Blend: 60% official course score (SQL) + 40% project score (MongoDB)
    merged["overall"] = (merged["score_pct"] * 0.6 + merged["project_score"] * 0.4).round(1)
    merged["band"] = merged["overall"].apply(band)

    # ---- Per-course detail --------------------------------------------------
    print("Course-level detail")
    header = (f"{'Student':<15}{'Course':<16}{'Teacher':<15}"
              f"{'Score':>6}{'Proj':>6}{'Overall':>9}  Band")
    print(header)
    print("-" * (len(header) + 8))
    detail = merged.sort_values(["student", "course"])
    for r in detail.itertuples():
        print(f"{r.student:<15}{r.course:<16}{r.teacher:<15}"
              f"{r.score:>6.2f}{r.project_score:>6.0f}{r.overall:>9.1f}  {r.band}")

    # ---- Per-student summary with a unit-weighted GPA ----------------------
    # GPA = sum(score x course_unit) / sum(course_unit), straight from SQL data
    merged["weighted"] = merged["score"] * merged["course_unit"]
    summary = merged.groupby(["student_id", "student", "graduated"], as_index=False).agg(
        courses=("course_id", "count"),
        units=("course_unit", "sum"),
        weighted=("weighted", "sum"),
        avg_project=("project_score", "mean"),
        feedback=("feedback_comments", "sum"),
    )
    summary["gpa"] = (summary["weighted"] / summary["units"]).round(2)
    summary["avg_project"] = summary["avg_project"].round(1)
    summary = summary.sort_values("gpa", ascending=False)

    print(f"\nStudent summary (GPA out of {SCORE_SCALE:.2f}, weighted by course_unit)")
    header = f"{'Student':<15}{'Courses':>8}{'Units':>7}{'GPA':>7}{'Avg Proj':>10}{'Feedback':>10}  Graduated"
    print(header)
    print("-" * (len(header) + 2))
    for r in summary.itertuples():
        print(f"{r.student:<15}{r.courses:>8}{r.units:>7}{r.gpa:>7.2f}"
              f"{r.avg_project:>10.1f}{r.feedback:>10}  {'Yes' if r.graduated else 'No'}")

    # ---- Teacher view: who needs support in their classes ------------------
    print("\nStudents below Merit (Pass / Needs Support), by teacher:")
    at_risk = merged[merged["band"].isin(["Needs Support", "Pass"])]
    if at_risk.empty:
        print("   none")
    for teacher, grp in at_risk.groupby("teacher"):
        names = ", ".join(f"{r.student} ({r.course_id})" for r in grp.itertuples())
        print(f"   {teacher:<15} {names}")

    detail.to_csv("learnnest_course_report.csv", index=False)
    summary.drop(columns=["weighted"]).to_csv("learnnest_student_summary.csv", index=False)
    print("\nSaved learnnest_course_report.csv and learnnest_student_summary.csv")


# =============================================================================
# MAIN
# =============================================================================

def main():
    conn = get_sql_connection()
    client = None
    try:
        if "--seed" in sys.argv:
            seed_sql(conn)
        audit_sql(conn)

        client, db = get_mongo_db()
        setup_mongo(db)
        # crud_operations(db, conn)
        # query_and_optimise(db)
        # merged = integrate_with_sql(db, conn)
        # build_report(merged)
    finally:
        if client:
            client.close()
        conn.close()


if __name__ == "__main__":
    main()
