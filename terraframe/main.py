from terraframe import Terraframe


if __name__ == "__main__":
    project_path = "/Users/andrelima/Personal/portfolio_projects/terraframe/tests/projects/my_project_2"
    t = Terraframe(project_path_str=project_path)
    t.process_deployments()
