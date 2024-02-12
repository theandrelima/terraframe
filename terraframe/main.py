import os
import json
from terraframe import Terraframe
from pathlib import Path
from pydantic_wrangler.dumpers import *
from pydantic_wrangler.utils import convert_src_file_to


if __name__ == "__main__":
    # TODO: receive project_path from CLI
    # project_path = "/Users/andrelima/Personal/portfolio_projects/terraframe/terraframe/tests/terraform/projects/my_project"
    os.environ["TEMPLATES_DIR"] = "/home/limaa13/projects/theandrelima_github/terraframe/terraframe/templates"
    project_path = "/home/limaa13/projects/theandrelima_github/terraframe/terraframe/tests/terraform/projects/my_project"
    t = Terraframe(project_folder_path_str=project_path)

    # with open(Path("data_records.txt"), "w") as f:
    #     f.write(json.dumps(t._data_store.as_dict().get("DeploymentModel"), indent=4))

    json_dumper(t._data_store.as_dict(), "data_records.json")

    # ini_dumper(t._data_store.as_dict(), "data_records.ini")

    toml_dumper(t._data_store.as_dict(), "data_records.toml")

    yaml_dumper(t._data_store.as_dict(), "data_records.yaml")

    convert_src_file_to("data_records.json", "yaml", "data_records_json_to_yaml.yaml")    

    t.process_deployments()
