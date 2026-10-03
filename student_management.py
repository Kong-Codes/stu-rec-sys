# students = {
    # "Stu101":{
    # "Name": "Tega",
    # "Age": "29",
    # "Courses": ["Python", "Sql"],
    # "Scores": (85, 70),
    # "Graduated": False
    # }
# }

# Students

students = {"Stu101":{
    "Name": "Tega",
    "Age": "29",
    "Courses": ["Python", "Sql"],
    "Scores": [85, 70],
    "Graduated": False
    }
}

def main_menu():
    while True:
        print("-------- Welcome To Learnest --------")
        print("1. Student Login")
        print("2. Teachers Login")
        print("3. Exit")

        choice = int(input("Selct an Option: ").strip())

        if choice ==1:
            student_login()
        elif choice == 2:
            teachers_login()
        elif choice == 3:
            break
        else:
            print("Invalid input")

TEACHER_PASSSWORD = 'teacher123'
STUDENT_PASSWORD = 'student123'


def get_or_create_student(student_id, name=None):
    if student_id in students:
        return students[student_id]
    if not name:
        name = student_id
    students[student_id] = {
        "Name": name,
        "Age": 25,
        "Courses": [],
        "Scores": [],
        "Graduated": False
    }
    return students[student_id]

def register_course(student_id, courses:list=None):
    course = students[student_id]['Courses']
    score = students[student_id]['Scores']
    for c in courses:
        if c in course:
            print("This course has already been registered")
            return
    for c in courses:
        course.append(c)
        score.append(0)
    print("You've successfully added this course")


def drop_course(student_id, course_name=None):
    courses = students[student_id]['Courses']

    if course_name not in courses:
        print("You've not registerd this course")
        return
    courses.remove(course_name)
    print("You've successfully dropped this course.")


def get_results(student_id):
    if not students[student_id]['Courses']:
        print("You've not registered any cousre")
        return
    stu_data = [
        f"Results for {students[student_id]['Name']}",
        f"Age: {students[student_id]['Age']}",
        f"Graduated: {students[student_id]['Graduated']}",
        "Courses and Scores:"
    ]
    courses = students[student_id]['Courses']
    scores = students[student_id]['Scores']
    for n in range(len(courses)):
        score_value = None
        course = None
        course = courses[n]
        score_value = scores[n]
        score_str = "N/A" if score_value is None else str(score_value)
        if score_str != "N/A":   
            stu_data.append(f"- {course}: {score_str}")
    return "\n".join(stu_data)


# Teachers
# Helper function
def assign(student_id, course, score):
    courses = students[student_id]['Courses']
    scores = students[student_id]['Scores']

    if course in courses:
        position = courses.index(course)
        scores[position] = score

def set_student_score():
    student_id = input("Enter Student Id: ").strip()
    name = input("Name: ").strip()
    course_name = input("Course name: ").strip()

    if not course_name:
        print("course name cannot be empty")
        return
    try:
        score = input("Enter score (0-100): ").strip()
        score = float(score)
        if not 0 <= score <= 100:
            print("Score must be between 0 and 100")
            return
    except ValueError:
        print("Invalid score. Please enter a number.")

    students = get_or_create_student(student_id, name)
    assign(student_id, course_name, score)

    print(students)

# score_set = set_student_score()

def view_student_result():
    student_id = input("Enter Student ID: ").strip()
    if student_id not in students:
        print("Student ID does not exist")
        return
    print(((get_results(student_id))))

def view_all_results():
    if not students:
        print("There are no registered students in the system")
        return
    print("---------All Students---------")
    for stu in students:
        print(get_results(stu))
        print("-"*25)


# Command line interface

def teachers_menu():
    while True:
        print('----------- Admin Dashboard ----------')
        print("1. Assign/update score")
        print("2. view student result")
        print("3. view all student result")
        print("4. logout")

        choice = int(input("Selct an option: ").strip())

        if choice == 1:
            set_student_score()
        elif choice == 2:
            view_student_result()
        elif choice == 3:
            view_all_results()
        elif choice == 4:
            print("Logging out.....")
            break
        else:
            print("Invalid input")

def student_menu(student_id):
    while True:
            print(f"----------- {students[student_id]['Name']}'s Dashboard ----------")
            print("1. Register a course")
            print("2. Drop a course")
            print("3. view my result")
            print("4. logout")
    
            choice = int(input("Selct an option: ").strip())
    
            if choice == 1:
                course = input("Course name: ")
                courselist = course.split()
                register_course(student_id, courselist)
            elif choice == 2:
                course = input("Course name: ")
                drop_course(student_id, course)
            elif choice == 3:
                print(get_results(student_id))
            elif choice == 4:
                print("Logging out.....")
                break
            else:
                print("Invalid input")

def student_login():
    student_id = input("Student_ID: ").strip()
    name = input("Name: ").strip()
    pwd = input("Password: ").strip()

    if pwd != STUDENT_PASSWORD:
        print("Invalid password")
        return
    get_or_create_student(student_id, name)
    print(f"Student login succesfull, welcome {students[student_id]['Name']}")
    student_menu(student_id)

def teachers_login():
    pwd = input("Password: ").strip()

    if pwd != TEACHER_PASSSWORD:
        print("Invalid password")
        return
    teachers_menu()


if __name__ == "__main__":
    main_menu()