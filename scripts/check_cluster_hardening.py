"""Valide les trois Deployments, rendus ou lus sur le cluster, au format JSON."""

import json
import sys


EXPECTED = {
    "coredns": ("coredns", "rancher/mirrored-coredns-coredns:1.14.7", 65532),
    "metrics-server": ("metrics-server", "rancher/mirrored-metrics-server:v0.9.0", 1000),
    "local-path-provisioner": (
        "local-path-provisioner", "rancher/local-path-provisioner:v0.0.37", 10001
    ),
}


def read_resources(stream):
    """kubectl get renvoie une List ; kubectl create peut juxtaposer des objets."""
    content = stream.read()
    decoder = json.JSONDecoder()
    index = 0
    items = []
    while index < len(content):
        if content[index].isspace():
            index += 1
            continue
        resource, index = decoder.raw_decode(content, index)
        if not isinstance(resource, dict):
            raise ValueError("Une ressource Kubernetes doit être un objet JSON")
        if "items" in resource:
            if not isinstance(resource["items"], list):
                raise ValueError("Liste de ressources invalide")
            items.extend(resource["items"])
        else:
            items.append(resource)
    if not items:
        raise ValueError("Aucune ressource Kubernetes reçue")
    return {"items": items}


def validate(document):
    deployments = {
        item["metadata"]["name"]: item
        for item in document["items"]
        if item.get("kind") == "Deployment"
        and item.get("metadata", {}).get("namespace") == "kube-system"
    }
    for name, (container_name, image, uid) in EXPECTED.items():
        deployment = deployments.get(name)
        if deployment is None:
            raise ValueError(f"Deployment absent : {name}")
        pod = deployment["spec"]["template"]["spec"]
        context = pod.get("securityContext", {})
        if context.get("runAsNonRoot") is not True or context.get("runAsUser") != uid:
            raise ValueError(f"Utilisateur du Pod incorrect : {name}")
        if context.get("seccompProfile", {}).get("type") != "RuntimeDefault":
            raise ValueError(f"Seccomp absent : {name}")
        if pod.get("initContainers") or len(pod.get("containers", [])) != 1:
            raise ValueError(f"Conteneurs inattendus : {name}")
        container = pod["containers"][0]
        if container["name"] != container_name or container["image"] != image:
            raise ValueError(f"Image ou conteneur inattendu : {name}")
        security = container.get("securityContext", {})
        effective = {**context, **security}
        if effective.get("runAsNonRoot") is not True or effective.get("runAsUser") != uid:
            raise ValueError(f"Utilisateur effectif incorrect : {name}")
        if effective.get("seccompProfile", {}).get("type") != "RuntimeDefault":
            raise ValueError(f"Seccomp effectif incorrect : {name}")
        if security.get("allowPrivilegeEscalation") is not False:
            raise ValueError(f"Élévation des privilèges autorisée : {name}")
        if security.get("readOnlyRootFilesystem") is not True:
            raise ValueError(f"Système de fichiers modifiable : {name}")
        if security.get("privileged", False):
            raise ValueError(f"Conteneur privilégié : {name}")
        if name != "metrics-server":
            capabilities = security.get("capabilities", {})
            if "ALL" not in {value.upper() for value in capabilities.get("drop", [])}:
                raise ValueError(f"Capacités non retirées : {name}")
            expected_add = ["NET_BIND_SERVICE"] if name == "coredns" else []
            if capabilities.get("add", []) != expected_add:
                raise ValueError(f"Capacités ajoutées inattendues : {name}")
        if name == "coredns":
            rolling = deployment["spec"]["strategy"]["rollingUpdate"]
            if rolling.get("maxUnavailable") != 0 or rolling.get("maxSurge") != 1:
                raise ValueError("La mise à jour DNS doit conserver un Pod disponible")


if __name__ == "__main__":
    try:
        validate(read_resources(sys.stdin))
    except (ValueError, KeyError, TypeError) as error:
        print(f"Durcissement invalide : {error}", file=sys.stderr)
        sys.exit(1)
    print("Durcissement des trois composants conforme.")
