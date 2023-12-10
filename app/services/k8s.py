import os
import uuid

from kubernetes import config, client
from sqlalchemy.orm import Session

from app import crud, models, schemas


class K8sService:
    def __init__(self, cluster: bool):
        self.api_crd = client.CustomObjectsApi()

        self.__namespace = os.getenv("GAME_SERVER_NAMESPACE")

        if not self.__namespace:
            service_account_base_dir = "/var/run/secrets/kubernetes.io/serviceaccount/"

            # Load namespace
            if cluster:
                namespace_path = service_account_base_dir + "namespace"
                try:
                    with open(namespace_path, "r") as namespace_file:
                        self.__namespace = namespace_file.read()
                except OSError:
                    print(f"failed to open {namespace_path}")
            else:
                self.__namespace = "veverse-gs"

    def list_servers(self):
        return self.api_crd.list_namespaced_custom_object(group="stable.veverse.com", version="v1", namespace=self.__namespace, plural="gameservers")

    def create_server(self, db: Session, requester: models.User, space_id: str):
        id = uuid.uuid4()
        max_players = 100
        name = "gs-" + id.hex
        image = os.getenv("GAME_SERVER_IMAGE")
        env = os.getenv('ENVIRONMENT')
        if env == 'test':
            image += '-test'
        elif env == 'prod':
            image += '-prod'
        api_key = os.getenv("GAME_SERVER_KEY")
        api_email = os.getenv("GAME_SERVER_EMAIL")
        api_password = os.getenv("GAME_SERVER_PASSWORD")
        host = os.getenv("GAME_SERVER_HOST")

        space = crud.space.get(db=db, requester=requester, id=space_id)
        if not space:
            raise ValueError("failed to find a space")

        environment = os.getenv('ENVIRONMENT') or 'dev'
        if environment != 'prod':
            host = f"{environment}.{host}"

        server_source = {
            "id": id.hex,
            "public": True,
            "host": host,
            "port": 0,  # assigned by the server controller
            "space_id": space_id,
            "max_players": max_players,  # todo: this has to be determined on the allowed server player amount for the requester
            "map": space.map,
            "game_mode": space.game_mode,
            "user_id": requester.id,
            "build": None,  # Not used
            "status": "created",  # assigned by the server controller
            "name": name,
            "image": image,
        }

        schema = schemas.ServerCreate(**server_source)

        # throws
        server: models.Server = crud.server.register(db=db, create_data=schema, requester=requester)
        if not server:
            raise ValueError("failed to create a server for the requester")

        image_pull_secrets = "registrysecret"

        cfg = {
            "apiVersion": "stable.veverse.com/v1",
            "kind": "GameServer",
            "metadata": {
                "name": name,
                "labels": {
                    "app": name
                }
            },
            "spec": {
                "image": image,
                "imagePullSecrets": [
                    {
                        "name": image_pull_secrets
                    }
                ],
                "settings": {
                    "serverId": id.hex,
                    "serverName": name,
                    "host": host,
                    "apiKey": api_key,
                    "maxPlayers": max_players,
                    "spaceId": space_id,
                    "apiEmail": api_email,
                    "apiPassword": api_password
                },
                "env": []
            }
        }

        return {
            "model": server, "resource": self.api_crd.create_namespaced_custom_object(group="stable.veverse.com", version="v1", namespace=self.__namespace, plural="gameservers", body=cfg)
        }

    def delete_server(self, server_id: str):
        id = uuid.UUID(server_id)
        return {
            "resource": self.api_crd.delete_namespaced_custom_object(group="stable.veverse.com", version="v1", namespace=self.__namespace, plural="gameservers", name="gs-" + id.hex)
        }


try:
    config.load_incluster_config()
    k8sServiceInstance = K8sService(cluster=True)
except config.ConfigException:
    print("not in the k8s cluster, k8s service can be unusable")
    config.load_kube_config()
    k8sServiceInstance = K8sService(cluster=False)
