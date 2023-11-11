from terraframe import Terraframe


if __name__ == "__main__":
    # TODO: receive project_path from CLI
    project_path = "/Users/andrelima/Personal/portfolio_projects/terraframe/tests/projects/my_project"
    t = Terraframe(project_path_str=project_path)
    t.process_deployments()
