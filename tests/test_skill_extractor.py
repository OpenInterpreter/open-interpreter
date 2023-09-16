import sys
sys.path.append("..")

from interpreter.skill_extractor import print_format_skill


def test_print_format_skill():
    # create a print hello world skill as test case
    skill_obj = {
        "skill_name": "print_hello_world",
        "skill_description": "print hello world",
        "skill_parameters": [
            {
                "param_name": "name",
                "param_type": "string",
                "param_description": "the name of the person",
                "param_required": True,
                "param_default": "world"
            }
        ],
        "skill_usage_example": "print_hello_world(name='world')",
        "skill_return": {
            "return_name": "result",
            "return_type": "string",
            "return_description": "the result of the skill"
        },
        "skill_tags": ["test"],
        "skill_dependencies": [],
        "skill_code": """
def print_hello_world(name):
    return f"hello {name}"
""",
        "skill_program_language": "python",
        "skill_metadata": {
            "created_at": "2020-01-01",
            "author": "test",
            "updated_at": "2020-01-01",
            "usage_count": 0,
        }
    }

    print_format_skill(skill_obj)
