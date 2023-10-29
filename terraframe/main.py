from terraframe import Terraframe


if __name__ == "__main__":
    project_path = (
        "/Users/andrelima/python_projects/terraframe/tests/projects/my_project"
    )
    t = Terraframe(project_path_str=project_path)
    t.process_deployments()
