"""
Student Records system

requirements:
- Student
    - Name
    - Age
    - Id
    - Graduated
    - Courses
    - Scores

- Teachers(Admins)
    - Name
    - Level

How it works
students creates account on the school platform, 
Teachers update students record, scores, 
Students registers courses,
Teachers assign scores
Students view their results 
"""

students = {
    "Stu101":{
    "Name": "Tega",
    "Age": "29",
    "Courses": ["Python", "Sql"],
    "Scores": (85, 70),
    "Graduated": False
    },

    "Stu102":{
        "Name": "Daniel",
        "Age": "29",
        "Courses": ["Sql", "Pandas"],
        "Scores": (85, 70),
        "Graduated": False
    },

    "Stu103":{
        "Name": "Purva",
        "Age": "29",
        "Courses": ['Python', "Databases"],
        "Scores": (85, 70),
        "Graduated": False
    }

}

# print(rank)

print(students['Stu101'])

# print(f"""Final results: 
#     Student: {students['Stu101']['Name']}
#     status: Graduated = {students['Stu101']['Graduated']}
#     ---------------------------------------------------------------------------
#     course: {students['Stu101']['Courses'][0]} - {students['Stu101']['Scores'][0]}
#     course: {students['Stu101']['Courses'][1]} - {students['Stu101']['Scores'][1]}
# """)

# print(f"""Final results: 
#     Student: {students['Stu102']['Name']}
#     status: Graduated = {students['Stu103']['Graduated']}
#     ---------------------------------------------------------------------------
#     course: {students['Stu102']['Courses'][0]} - {students['Stu102']['Scores'][0]}
#     course: {students['Stu102']['Courses'][1]} - {students['Stu102']['Scores'][1]}
# """)

# print(f"""Final results: 
#     Student: {students['Stu103']['Name']}
#     status: Graduated = {students['Stu103']['Graduated']}
#     ---------------------------------------------------------------------------
#     course: {students['Stu103']['Courses'][0]} - {students['Stu103']['Scores'][0]}
#     course: {students['Stu103']['Courses'][1]} - {students['Stu103']['Scores'][1]}
# """)

print(students['Stu101'])
