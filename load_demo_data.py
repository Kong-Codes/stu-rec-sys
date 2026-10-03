"""
Loads the LearnNest demo data into MongoDB.

Files (MongoDB Extended JSON, so dates and ObjectIds keep their real types):
    project_submissions.json  11 docs  - one per final_grades row in PostgreSQL
    mentor_feedback.json      11 docs  - threads referencing project_submissions._id
    activity_logs.json       570 docs  - logins, lessons, videos, quizzes, forum posts, uploads

The IDs match the PostgreSQL seed data (STU001-STU006, TCH001-TCH003,
PY101 / SQL201 / DE301), so everything joins back to SQL.

Run:   python load_demo_data.py
Or, without Python (MongoDB Database Tools):
    mongoimport --db learnnest --collection project_submissions --jsonArray --drop --file project_submissions.json
    mongoimport --db learnnest --collection mentor_feedback     --jsonArray --drop --file mentor_feedback.json
    mongoimport --db learnnest --collection activity_logs       --jsonArray --drop --file activity_logs.json
Or in MongoDB Compass: open a collection > Add Data > Import JSON.
"""

import os
from pathlib import Path

from bson.json_util import loads
from pymongo import ASCENDING, DESCENDING, MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
HERE = Path(__file__).parent


def main():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client["learnnest"]

    for name in ["project_submissions", "mentor_feedback", "activity_logs"]:
        docs = loads((HERE / f"{name}.json").read_text())
        db.drop_collection(name)
        db[name].insert_many(docs)
        print(f"{name:<20} {db[name].count_documents({}):>4} documents loaded")

    # Indexes for the common queries
    db.project_submissions.create_index([("student_id", ASCENDING), ("course_id", ASCENDING)], unique=True)
    db.mentor_feedback.create_index("submission_id")
    db.mentor_feedback.create_index([("teacher_id", ASCENDING), ("resolved", ASCENDING)])
    db.activity_logs.create_index([("student_id", ASCENDING), ("ts", DESCENDING)])
    db.activity_logs.create_index("event")

    # Quick sanity check: every feedback thread points at a real submission
    sub_ids = set(db.project_submissions.distinct("_id"))
    broken = [f["_id"] for f in db.mentor_feedback.find({}, {"submission_id": 1})
              if f["submission_id"] not in sub_ids]
    print("Feedback threads with a missing submission:", broken or "none")
    client.close()


if __name__ == "__main__":
    main()
