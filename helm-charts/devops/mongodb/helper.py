import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

import kubernetes.client
import kubernetes.config
import yaml
from google.api_core.exceptions import Conflict, NotFound
from google.cloud import compute_v1

# https://medium.com/@studio3t/secure-mongodb-with-x-509-tls-ssl-certificates-42ff4290d9f3
# https://dinfratechsource.wordpress.com/2018/12/16/securing-mongodb-with-x-509-authentication/
# https://www.bustedware.com/blog/mongodb-ssl-tls-x509-authentication


class MongoDB:
    def __init__(self, namespace, data, value_files):
        self.namespace = namespace  # merged_data.get("NAMESPACE", "").replace("_", "-")
        self.INFRASTRUCTURE = data.get("INFRASTRUCTURE", None)
        self.release_name = "mongodb"
        self.value_files = value_files
        self.statefulset_name = "mongo-db"
        self.replica_set_name = "rs0"
        self.chart_path = "."
        self.keyfile_secret_name = "mongodb-ssl"
        self.baseURL = data.get("MONGODB").get("baseURL")
        tempBaseUrl = self.baseURL.replace(".", "-")
        self.cert_dir = f"cert/{self.namespace}-{tempBaseUrl}"
        self.helm_release_name = self.release_name
        self.microserviceConnectionURL: list = data.get("MONGODB").get("microserviceConnectionURL")
        # self.externalBaseURL = data.get("MONGODB").get("externalBaseURL")

        self.port = data.get("MONGODB").get("MONGO_PORT")
        self.MONGO_USERNAME = data.get("MONGODB").get("MONGO_USERNAME")
        self.MONGO_PASSWORD = data.get("MONGODB").get("MONGO_PASSWORD")
        self.MONGO_ROOT_USERNAME = data.get("MONGODB").get("MONGO_ROOT_USERNAME")
        self.MONGO_ROOT_PASSWORD = data.get("MONGODB").get("MONGO_ROOT_PASSWORD")
        self.pod_count = data.get("MONGODB").get("MONGO_REPLICA")
        self.ssl_path = data.get("MONGODB").get("ssl_path")
        self.ssl_ca_pem = "ca.pem"  # data.get("MONGODB").get("ssl_ca_pem")
        self.ssl_client_pem = "client.pem"  # data.get("MONGODB").get("ssl_client_pem")
        self.ssl_member_pem = "node.pem"  # data.get("MONGODB").get("ssl_member_pem")
        self.core_api, self.apps_api = load_kubernetes_config()

        # self.microserviceConnectionURL = [
        #     item.replace("{{ .Values.MONGODB.Namespace }}", self.namespace)
        #     for item in self.microserviceConnectionURL
        # ]

        print(f"==> files          : {self.value_files}")
        print(f"==> namespace      : {self.namespace}")
        print(f"==> namespace      : {self.cert_dir}")
        print(f"==> microservice   : {self.microserviceConnectionURL}")
        if not self.core_api or not self.apps_api:
            return

    def __is_ip__(self, ip):
        """Check if a string is a valid IP address."""
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False

    def __generate_mongo_certificates__(self, sys_ip_list=[], password="password"):
        """Generates MongoDB certificates, ensuring correct SANs and key
        identifiers."""
        os.makedirs(self.cert_dir, exist_ok=True)  # Create directory if it doesn't exist

        days_valid = 3650
        common_subj = "/CN=server/OU=MONGO/O=UPSWING/L=PUNE/ST=MH/C=IN"
        client_subj = "/CN=DbUser/OU=MONGO_CLIENTS/O=UPSWING/L=MH/ST=PN/C=IN"

        # Generate CA certificate
        ca_key = os.path.join(self.cert_dir, "ca_private.pem")
        ca_crt = os.path.join(self.cert_dir, self.ssl_ca_pem)
        if not os.path.isfile(ca_crt):
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:4096",
                    "-nodes",
                    "-keyout",
                    ca_key,
                    "-out",
                    ca_crt,
                    "-subj",
                    common_subj,
                    "-passout",
                    f"pass:{password}",
                    "-days",
                    str(days_valid),
                    "-addext",
                    "basicConstraints = CA:TRUE",
                    "-addext",
                    "keyUsage = keyCertSign, cRLSign",
                    "-addext",
                    "subjectKeyIdentifier = hash",
                    "-addext",
                    "authorityKeyIdentifier = keyid,issuer",
                ],
                check=True,
            )

        # Generate node & client certificates
        for entity, subj in [("node", common_subj), ("client", client_subj)]:
            key_file = os.path.join(self.cert_dir, f"{entity}.key")
            csr_file = os.path.join(self.cert_dir, f"{entity}.csr")
            crt_file = os.path.join(self.cert_dir, f"{entity}.crt")
            pem_file = os.path.join(self.cert_dir, f"{entity}.pem")

            if os.path.isfile(pem_file):
                print(f"PEM file for {entity} already exists. Skipping...")
                continue

            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    key_file,
                    "-out",
                    csr_file,
                    "-subj",
                    subj,
                ],
                check=True,
            )

            # Generate node certificate with SANs (critical for fixing the mismatch)
            dns_list = {
                f"mongodb-svc.{self.namespace}.svc.cluster.local",
                f"mongodb-svc.{self.namespace}",
                f"mongo-service.{self.namespace}.svc.cluster.local",
                f"mongo-service.{self.namespace}",
                "localhost",
                # Add your MongoDB service's external DNS name here if applicable (e.g., "my-mongodb.example.com")
            }

            ip_list = {"127.0.0.1"}  # Include MongoDB service IP

            for i in range(self.pod_count):
                dns_list.add(
                    f"{self.microserviceConnectionURL[i].split(':')[0]}"
                    # f"{self.statefulset_name}-{i}.mongodb-svc.{self.namespace}.svc.cluster.local"
                )
                # dns_list.add(f"{self.statefulset_name}-{i}.mongodb-svc.{self.namespace}")
                # dns_list.add(f"{self.statefulset_name}-{i}.{self.externalBaseURL}")

            for ip in self.microserviceConnectionURL:
                ip = ip.split(":")[0]
                if self.__is_ip__(ip):
                    if ip not in ip_list:
                        ip_list.add(ip)
                else:
                    if ip not in dns_list:
                        dns_list.add(ip)

            for ip in sys_ip_list:
                if self.__is_ip__(ip):
                    if ip not in ip_list:
                        ip_list.add(ip)
                else:
                    if ip not in dns_list:
                        dns_list.add(ip)

            san = "".join([f"DNS:{name}," for name in dns_list] + [f"IP:{ip}," for ip in ip_list])[
                :-1
            ]  # Remove last comma

            with tempfile.NamedTemporaryFile(mode="w", delete=False) as ext_file:
                ext_file.write(
                    f"""
                    authorityKeyIdentifier=keyid,issuer
                    basicConstraints=CA:FALSE
                    keyUsage=digitalSignature,keyEncipherment
                    extendedKeyUsage=serverAuth,clientAuth
                    subjectAltName={san}
                """
                )
                ext_file_path = ext_file.name

            subprocess.run(
                [
                    "openssl",
                    "x509",
                    "-req",
                    "-sha256",
                    "-days",
                    str(days_valid),
                    "-in",
                    csr_file,
                    "-CA",
                    ca_crt,
                    "-CAkey",
                    ca_key,
                    "-CAcreateserial",
                    "-extfile",
                    ext_file_path,
                    "-out",
                    crt_file,  # Use .crt extension
                ],
                check=True,
            )

            os.remove(ext_file_path)
            # Combine certificate and key into PEM file
            subprocess.run(f"cat {crt_file} {key_file} > {pem_file}", shell=True, check=True)

        def read_file_content(file_path):
            with open(file_path, "rb") as file:
                return base64.b64encode(file.read()).decode("utf-8")

        ca_pem_content = read_file_content(ca_crt)
        node_pem_content = read_file_content(os.path.join(self.cert_dir, self.ssl_member_pem))
        client_pem_content = read_file_content(os.path.join(self.cert_dir, self.ssl_client_pem))

        # Generate the YAML data with the file contents
        yaml_data = {
            "MONGODB": {
                "ssl_ca_pem": ca_pem_content,
                "ssl_member_pem": node_pem_content,
                "ssl_client_pem": client_pem_content,
            }
        }

        # Write YAML data to file
        yaml_file_path = os.path.join(f"{self.cert_dir}/certificates.yaml")
        with open(yaml_file_path, "w") as yaml_file:
            yaml.dump(yaml_data, yaml_file, default_flow_style=False)
        print(f"YAML file generated at: {yaml_file_path}")

    def __install_or_upgrade_helm_chart__(self, ip_list=[]):
        """Installs or upgrades a Helm chart."""
        new_install = False
        try:
            subprocess.run(
                ["helm", "status", self.helm_release_name, "-n", self.namespace], check=True
            )
            print(f"Upgrading Helm release '{self.helm_release_name}'...")
            cmd = (
                ["helm", "upgrade", self.helm_release_name, self.chart_path]
                + self.value_files
                + ["-f", f"{self.cert_dir}/certificates.yaml", "-n", self.namespace]
            )
        except subprocess.CalledProcessError:
            new_install = True
            print(f"Helm release '{self.helm_release_name}' not found. Installing...")
            # Create or update the keyfile Secret
            self.__generate_mongo_certificates__(ip_list)
            cmd = (
                ["helm", "install", self.helm_release_name, self.chart_path]
                + self.value_files
                + ["-f", f"{self.cert_dir}/certificates.yaml", "-n", self.namespace]
            )
        subprocess.run(cmd, check=True)
        print(
            f"Helm chart '{self.helm_release_name}' {'INSTALLED' if new_install else 'UPGRADED'} successfully."
        )
        return new_install

    def __wait_for_pods__(self, timeout_seconds=1800):
        """Waits for all pods in a StatefulSet to be ready and returns their
        info."""
        print("Waiting for all MongoDB pods to be ready...")
        start_time = time.time()
        while True:
            pods = self.core_api.list_namespaced_pod(
                namespace=self.namespace, label_selector=f"app={self.statefulset_name}"
            )
            pod_info = [{"name": pod.metadata.name, "ip": pod.status.pod_ip} for pod in pods.items]

            if len(pod_info) != self.pod_count:
                print(
                    f"Waiting for all pods to be created... (Found {len(pod_info)}/{self.pod_count} pods)"
                )
                time.sleep(5)
                continue  # Check again after 5 seconds

            # Check readiness only if all pods are created and have IP addresses
            all_ready = all(
                pod.status.pod_ip is not None
                and any(
                    condition.status == "True"
                    for condition in pod.status.conditions
                    if condition.type == "Ready"
                )
                for pod in pods.items
            )

            if all_ready:
                print("All MongoDB pods are ready.")
                return pod_info  # Return the pod_info list
            if time.time() - start_time > timeout_seconds:
                print("Timeout waiting for pods to be ready.")
                return None

            print(f"Waiting... (Found {len(pod_info)}/{self.pod_count} ready pods)")
            time.sleep(5)

    def __initialize_or_reconfigure_replica_set__(
        self, target_pod_name, replica_ip_list=[], use_auth=False, force=False
    ) -> bool:
        """Initializes or reconfigures the MongoDB replica set."""
        if len(replica_ip_list) > 0:
            expected_rs_config = {
                "_id": self.replica_set_name,
                "version": 1,
                "members": [
                    {"_id": i, "host": f"{ip}:{self.port}"} for i, ip in enumerate(replica_ip_list)
                ],
            }
        else:
            expected_rs_config = {
                "_id": self.replica_set_name,
                "version": 1,
                "members": [
                    {
                        "_id": i,
                        "host": f"{self.microserviceConnectionURL[i]}",
                        # "host": f"{self.statefulset_name}-{i}.{self.externalBaseURL}:{self.port}",
                        # "host": f"{self.statefulset_name}-{i}.mongodb-svc.{self.namespace}:{self.port}",
                        # "host": f"{self.statefulset_name}-{i}.mongodb-svc.{self.namespace}.svc.cluster.local:{self.port}",
                    }
                    for i in range(self.pod_count)
                ],
            }

        expected_member_hosts = set(
            [member.get("host") for member in expected_rs_config.get("members", [])]
        )

        try:
            # Check replica set status and configuration
            get_rs_config_command = [
                "kubectl",
                "exec",
                target_pod_name,
                "-n",
                self.namespace,
                "--",
                "mongosh",
                "--quiet",
                f"localhost:{self.port}/admin",
                "--tls",
                "--tlsCAFile",
                f"{self.ssl_path}/{self.ssl_ca_pem}",
                "--tlsCertificateKeyFile",
                f"{self.ssl_path}/{self.ssl_client_pem}",
                "--eval",
                '"JSON.stringify({members: rs.conf().members, version: rs.conf().version}, null, 2)"',
            ]

            # Conditionally add authentication parameters
            if use_auth:
                get_rs_config_command.extend(
                    ["--username", self.MONGO_ROOT_USERNAME, "--password", self.MONGO_ROOT_PASSWORD]
                )

            result = subprocess.run(get_rs_config_command, capture_output=True, text=True)

            actual_rs_info = {"members": [], "version": 1}
            if result.returncode == 0 and result.stdout:
                actual_rs_info = json.loads(result.stdout)
                actual_member_hosts = {member["host"] for member in actual_rs_info.get("members")}
            else:
                print(result.returncode)
                print(result.stdout)
                actual_member_hosts = set()

            print("Expected:", expected_member_hosts)
            print("Actual:", actual_member_hosts)

            # Compare sets of member hosts (order doesn't matter)
            if expected_member_hosts == actual_member_hosts and not force:
                print("Replica set members are correct. No changes needed.")
                return True  # No need to reconfigure if members are already correct

            print("Replica set members need update. Reconfiguring/Initiating...")

            # Build the correct command for rs.initiate() or rs.reconfig()
            if actual_member_hosts:
                # Replica set exists, use rs.reconfig()
                expected_rs_config["version"] = actual_rs_info.get("version", 1) + 1
                command = f"rs.reconfig({json.dumps(expected_rs_config)}, {{force: true}})"
            else:
                # Replica set doesn't exist, use rs.initiate()
                command = f"rs.initiate({json.dumps(expected_rs_config)})"

            # Execute the command
            reconfig_command = [
                "kubectl",
                "exec",
                target_pod_name,
                "-n",
                self.namespace,
                "--",
                "mongosh",
                "--quiet",
                f"localhost:{self.port}/admin",
                "--tls",
                "--tlsCAFile",
                f"{self.ssl_path}/{self.ssl_ca_pem}",
                "--tlsCertificateKeyFile",
                f"{self.ssl_path}/{self.ssl_client_pem}",
                "--eval",
                command,
            ]
            # Conditionally add authentication parameters
            if use_auth:
                reconfig_command.extend(
                    ["--username", self.MONGO_ROOT_USERNAME, "--password", self.MONGO_ROOT_PASSWORD]
                )
            print(reconfig_command)
            subprocess.run(reconfig_command, check=True)
            print("Replica set reconfiguration/initialization complete.")

            # Verify replica set status after initialization or reconfiguration
            time.sleep(5)  # Allow some time for changes to propagate
            verification_result = subprocess.run(
                get_rs_config_command, capture_output=True, text=True
            )

            if verification_result.returncode == 0:
                new_actual_rs_info = json.loads(verification_result.stdout.strip())
                new_actual_member_hosts = {
                    member["host"] for member in new_actual_rs_info.get("members", [])
                }

                if expected_member_hosts == new_actual_member_hosts:
                    print("Replica set initialization/reconfiguration successful.")
                    print(f"Version: {expected_rs_config['version']}")
                    print(f"Members: {new_actual_member_hosts}")
                    time.sleep(10)  # Allow some time for changes to propagate
                    return True
                else:
                    print(
                        "WARNING: Replica set reconfiguration/initialization might not have been successful. Please verify manually."
                    )
                    return False
            else:
                print("Error verifying replica set configuration:", verification_result.stderr)
                return False

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return False
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {e.stderr}")
            return False

    def __get_primary_node__(self, auth_enabled=False) -> str:
        for i in range(self.pod_count):
            try:
                result = json.loads(
                    self.__run_kubectl_command__(
                        f"{self.statefulset_name}-0",
                        command='"JSON.stringify(rs.status(), null, 2)"',
                        auth_enabled=auth_enabled,
                    )
                )

                print("----------")
                print(result)

                for member in result.get("members"):
                    if member.get("stateStr") == "PRIMARY":
                        return member.get("_id")
            except Exception as e:
                print(f"failed to get primary info from pod: {i}, retrying...")
                print(e)

    def __create_default_user__(self, pod_name):
        """Creates default users in a MongoDB pod if they don't already
        exist."""

        def user_exists(user_id, output):
            """Checks if a user with the given ID exists in the output."""
            result = any(user.get("user") == user_id for user in output)
            if result:
                print(f"user {user_id} already exists")
            return result

        def create_user(user_command, success_message, error_message):
            """Creates a user using the provided command."""
            output = self.__run_kubectl_command__(pod_name, user_command)
            if output:
                print(success_message)
                return True
            else:
                print(error_message)
                print(output)
                return False

        # --- Cert User ---
        admin_user_command = (
            '"JSON.stringify(db.getSiblingDB("$external").getUsers().users, null, 2)"'
        )
        output = json.loads(self.__run_kubectl_command__(pod_name, admin_user_command))

        cert_user_id = "C=IN,ST=MH,L=PUNE,O=UPSWING,OU=MONGO_CLIENTS,CN=Admin"
        if not user_exists(cert_user_id, output):
            print("Creating cert user...")
            cert_user_command = (
                'db.getSiblingDB("$external").runCommand({createUser: "'
                + cert_user_id
                + '",roles: [{ role: "root", db: "admin" }]})'
            )
            success = create_user(
                cert_user_command, "Cert user created successfully.", "Failed to create cert user."
            )
            if not success:
                return False  # Exit if cert user creation fails

        # --- Admin User ---
        admin_user_command = '"JSON.stringify(db.getSiblingDB("admin").getUsers().users, null, 2)"'
        output = json.loads(self.__run_kubectl_command__(pod_name, admin_user_command))
        admin_user_id = self.MONGO_USERNAME
        if not user_exists(admin_user_id, output):  # Reuse output from previous check
            print("Creating admin user...")
            admin_user_command = (
                'db.getSiblingDB("admin").createUser({"user": "'
                + admin_user_id
                + '", "pwd": "'
                + self.MONGO_PASSWORD
                + '", "roles": [{ "role": "userAdminAnyDatabase", "db": "admin" }, { role: "readWriteAnyDatabase", db: "admin" }]})'
            )
            success = create_user(
                admin_user_command,
                "Admin user created successfully.",
                "Failed to create admin user.",
            )
            if not success:
                return False

        # --- Cluster Admin User ---
        root_user_id = self.MONGO_ROOT_USERNAME
        if not user_exists(root_user_id, output):  # Reuse output
            print("Creating cluster admin user...")
            admin_user_command = (
                'db.getSiblingDB("admin").createUser({"user" : "'
                + root_user_id
                + '", "pwd" : "'
                + self.MONGO_ROOT_PASSWORD
                + '", "roles": [{ "role" : "clusterAdmin", "db" : "admin" }, { role: "readWriteAnyDatabase", db: "admin" }]})'
            )
            success = create_user(
                admin_user_command,
                "Cluster admin user created successfully.",
                "Failed to create cluster user.",
            )
            if not success:
                return False

        return True  # All users created (or already existed) successfully

    def __upgrade_chart_security__(self):
        """Upgrade the Helm chart with authentication enabled."""
        command = (
            ["helm", "upgrade", self.helm_release_name, self.chart_path]
            + self.value_files
            + [
                "-f",
                f"{self.cert_dir}/certificates.yaml",
                "--set",
                "MONGODB.authentication=true",
                "--namespace",
                self.namespace,
            ]
        )
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command '{command}': {e.stderr}")

    def __run_kubectl_command__(self, pod, command, auth_enabled=False):
        full_command = [
            "kubectl",
            "exec",
            pod,
            "-n",
            self.namespace,
            "--",
            "mongosh",
            "--quiet",
            f"localhost:{self.port}",
            "--tls",
            "--tlsCAFile",
            f"{self.ssl_path}/{self.ssl_ca_pem}",
            "--tlsCertificateKeyFile",
            f"{self.ssl_path}/{self.ssl_client_pem}",
            "--eval",
            command,
        ]

        if auth_enabled:
            full_command.extend(
                ["--username", self.MONGO_ROOT_USERNAME, "--password", self.MONGO_ROOT_PASSWORD]
            )

        try:
            result = subprocess.run(full_command, capture_output=True, text=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error executing command '{command}': {e.stderr}")
            return None

    def __get_development_ips__(self):
        client = compute_v1.AddressesClient()
        existing_ips = []
        region = "asia-south1"
        project_id = "upswing-global"
        ip_names = [f"development-mongo-{i}" for i in range(self.pod_count)]

        # Check existing IP addresses
        for ip_name in ip_names:
            try:
                address = client.get(project=project_id, region=region, address=ip_name)
                existing_ips.append(address.address)
            except NotFound:
                pass

            # Create IP addresses if they do not exist
        created_ips = []
        for ip_name in ip_names:
            if not any(ip_name in ip for ip in existing_ips):
                address_resource = compute_v1.Address(
                    name=ip_name, address_type="EXTERNAL"  # Optional, can specify type if needed
                )
                try:
                    operation = client.insert(
                        project=project_id, region=region, address_resource=address_resource
                    )
                    operation.result()  # Wait for the operation to complete
                    created_address = client.get(project=project_id, region=region, address=ip_name)
                    created_ips.append(created_address.address)
                except Conflict:
                    print(f"The resource '{ip_name}' already exists, skipping creation.")

        return existing_ips + created_ips

    def __service_exists__(self, service_name):
        """Check if a Kubernetes service exists in the given namespace.

        Args:
            service_name (str): The name of the service

        Returns:
            bool: True if the service exists, False otherwise.
        """
        try:
            subprocess.run(
                ["kubectl", "get", "service", service_name, "-n", self.namespace],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def __create_service__(self, i, service_name, load_balancer_ip):
        """Create a LoadBalancer service in Kubernetes.

        Args:
            service_name (str): The name of the service.
            load_balancer_ip (str): The LoadBalancer IP for the service.

        Returns:
            None
        """
        service_yaml = f"""
    apiVersion: v1
    kind: Service
    metadata:
      name: {service_name}
      namespace: {self.namespace}
    spec:
      type: LoadBalancer
      loadBalancerIP: {load_balancer_ip}
      selector:
        statefulset.kubernetes.io/pod-name: {self.statefulset_name}-{i}
      ports:
      - protocol: TCP
        port: 27017
        targetPort: 27017
        """
        process = subprocess.Popen(
            ["kubectl", "apply", "-f", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate(input=service_yaml.encode())
        if process.returncode != 0:
            print(f"Failed to create service {service_name}: {stderr.decode()}")
        else:
            print(f"Service {service_name} created successfully")

    def __check_replica_set_status__(self, primary_node):
        try:
            # Define the command to check replica set status
            command = [
                "kubectl",
                "exec",
                primary_node,
                "--",
                "mongosh",
                "--quiet",
                f"localhost:{self.port}/admin",
                "--tls",
                "--tlsCAFile",
                f"{self.ssl_path}/{self.ssl_ca_pem}",
                "--tlsCertificateKeyFile",
                f"{self.ssl_path}/{self.ssl_client_pem}",
                "--username",
                f"{self.MONGO_ROOT_USERNAME}",
                "--password",
                f"{self.MONGO_ROOT_PASSWORD}",
                "--eval",
                "JSON.stringify(rs.status())",
            ]

            # Execute the command
            result = subprocess.run(command, capture_output=True, text=True)

            # Check if the command was successful
            if result.returncode != 0:
                print(f"Error executing command: {result.stderr}")
                return False

            # Parse the JSON output
            status = json.loads(result.stdout)

            # Check each member's state
            for member in status["members"]:
                state = member["stateStr"]
                if state not in ["PRIMARY", "SECONDARY"]:
                    print(f"Warning: Member {member['name']} is in state {state}")
                    return False

            print("Replica set is healthy")
            return True

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            return False

        except Exception as e:
            print(f"Error checking replica set status: {e}")
            return False

    def start_port_forward(self, port_to_use):
        try:
            node = self.__get_primary_node__(auth_enabled=True)
            print(f"Primary node id: {node}")

            command = [
                "kubectl",
                "port-forward",
                f"{self.statefulset_name}-{node}",
                f"{port_to_use}:{self.port}",
                "-n",
                self.namespace,
            ]
            # Start the port-forward command and keep it running
            process = subprocess.Popen(command)

            print("Port-forwarding started. Press Ctrl+C to stop.")

            # Wait for the process to finish
            process.wait()
        except KeyboardInterrupt:
            # Handle the termination gracefully when user interrupts with Ctrl+C
            print("\nPort-forwarding stopped by user.")
            process.terminate()
        except Exception as e:
            print(f"An error occurred: {e}")

    def gcp(self):
        self.__install_or_upgrade_helm_chart__()

        # 3. Wait for All Pods to be Ready and Get Pod Information
        pods_info = self.__wait_for_pods__()
        if not pods_info:
            return

        # 4. Check and Initialize/Reconfigure Replica Set
        self.post_deployment_setup()

    def aws(self):
        self.__install_or_upgrade_helm_chart__()

        pods_info = self.__wait_for_pods__()
        if not pods_info:
            return

        self.post_deployment_setup()

    def post_deployment_setup(self, use_auth=False, use_force=False):
        result = self.__initialize_or_reconfigure_replica_set__(
            target_pod_name=f"{self.statefulset_name}-0", use_auth=use_auth, force=use_force
        )

        if result:
            node = self.__get_primary_node__(auth_enabled=use_auth)
            print(f"Primary node id: {node}")

            # 6. Create user if installation is happening for the 1st time
            if node is not None and not use_auth:
                result = self.__create_default_user__(f"{self.statefulset_name}-{node}")
                if result:
                    self.__upgrade_chart_security__()
                else:
                    print("Auth is not enabled as default as there is issue with user creation")

    def recover_mongodb_data_from_pvc(self, local_folder):
        """Get all PVCs in the given namespace and return them as a list."""
        try:
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pvc",
                    "-n",
                    self.namespace,
                    "-o",
                    "custom-columns=NAME:.metadata.name",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            pvc_list = result.stdout.strip().split("\n")[1:]  # Skip the header "NAME"
        except subprocess.CalledProcessError as e:
            print(f"Error getting PVCs: {e}")
            return

        """Prompt user to choose a PVC from the list."""
        if not pvc_list:
            print("No PVCs found.")
            return None

        print("Available PVCs:")
        for idx, pvc in enumerate(pvc_list, 1):
            print(f"{idx}. {pvc}")

        choice = input("Enter the number of the PVC you want to recover data from: ")

        try:
            pvc_index = int(choice) - 1
            if 0 <= pvc_index < len(pvc_list):
                selected_pvc = pvc_list[pvc_index]
            else:
                print("Invalid selection.")
                return None
        except ValueError:
            print("Please enter a valid number.")
            return None

        # Step 1: Define the busybox pod manifest
        pod_manifest = f"""
    apiVersion: v1
    kind: Pod
    metadata:
      name: mongodb-pvc-recovery
      namespace: {self.namespace}
    spec:
      containers:
      - name: recovery-container
        image: busybox
        command: ["/bin/sh", "-c", "sleep 3600"]
        volumeMounts:
        - mountPath: /data/db
          name: mongodb-pvc
      volumes:
      - name: mongodb-pvc
        persistentVolumeClaim:
          claimName: {selected_pvc}
    """

        # Step 2: Create a temporary pod with PVC mounted
        pod_file = "mongodb-pvc-recovery.yaml"
        with open(pod_file, "w") as f:
            f.write(pod_manifest)

        print(f"Creating temporary busybox pod to access PVC {selected_pvc}...")
        subprocess.run(["kubectl", "apply", "-f", pod_file], check=True)

        # Step 3: Wait for the pod to be ready
        print("Waiting for the busybox pod to be ready...")
        while True:
            status = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pod",
                    "mongodb-pvc-recovery",
                    "-n",
                    self.namespace,
                    "-o",
                    "jsonpath={.status.phase}",
                ],
                capture_output=True,
                text=True,
            )
            if status.stdout.strip() == "Running":
                break
            time.sleep(5)

        # Step 4: Copy data from PVC to the local folder
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        print(f"Copying MongoDB data from PVC {selected_pvc} to local folder {local_folder}...")
        subprocess.run(
            ["kubectl", "cp", f"{self.namespace}/mongodb-pvc-recovery:/data/db", local_folder],
            check=True,
        )

        # Step 5: Cleanup the temporary pod
        print("Cleaning up the temporary pod...")
        subprocess.run(
            ["kubectl", "delete", "pod", "mongodb-pvc-recovery", "-n", self.namespace], check=True
        )
        os.remove(pod_file)

        print(f"MongoDB data has been successfully copied to {local_folder}")


def merge_yaml_files(filenames):
    """Merges multiple YAML files into a single dictionary.

    Args:
        filenames: A list of YAML file paths.

    Returns:
        A dictionary representing the merged YAML data.
    """

    merged_data = {}
    value_files = []

    for filename in filenames:
        try:
            with open(filename, "r") as f:
                data = yaml.safe_load(f)

                # Recursive merge for nested dictionaries
                def merge_dicts(d1, d2):
                    for k, v in d2.items():
                        if k in d1 and isinstance(v, dict) and isinstance(d1[k], dict):
                            d1[k] = merge_dicts(d1[k], v)
                        else:
                            d1[k] = v
                    return d1

                merged_data = merge_dicts(merged_data, data)
            value_files.extend(["-f", filename])
        except FileNotFoundError:
            print(f"Error: File not found - {filename}", file=sys.stderr)
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error loading YAML from {filename}: {e}", file=sys.stderr)
            sys.exit(1)

    return merged_data, value_files


def load_kubernetes_config():
    """Loads Kubernetes configuration."""
    try:
        kubernetes.config.load_kube_config()  # Load from default kubeconfig
        return kubernetes.client.CoreV1Api(), kubernetes.client.AppsV1Api()
    except kubernetes.config.ConfigException as e:
        print(f"Error loading Kubernetes config: {e}")
        return None, None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]
    else:
        print("Select Action:")
        # print("0. Install / Upgrade:")
        # print("1. Connect Direct:")
        print("2. Generate Certificates:")
        print("3. Post Deployment:")
        print("4. Recovery:")
        action = input("Enter value: ")

    namespace = input("Enter namespace to use: ")
    # chart_path = input("chart path")
    filenames = input("Enter files: ")
    filenames = filenames.split(",")
    filenames = ["values.yaml"] + filenames
    # print(chart_path)
    print(filenames)

    if not filenames:
        print("Usage: python merge_yaml.py <file1.yaml> <file2.yaml> ...", file=sys.stderr)
        sys.exit(1)
    merged_data, value_files = merge_yaml_files(filenames)
    mongodb = MongoDB(namespace, merged_data, value_files)
    # mongodb.chart_path = chart_path
    if action == "0":
        if mongodb.INFRASTRUCTURE == "gcp":
            mongodb.gcp()
        elif mongodb.INFRASTRUCTURE == "aws":
            mongodb.aws()
        else:
            print(f"Invalid Infra {mongodb.INFRASTRUCTURE} provided")
    elif action == "1":
        port = input("Enter port number of your machine to use: ")
        mongodb.start_port_forward(port)
    elif action == "2":
        mongodb.__generate_mongo_certificates__()
    elif action == "3":
        use_auth = input("Use auth (y/n): ")
        force = input("Use force (y/n): ")
        mongodb.post_deployment_setup(use_auth=(use_auth == "y"), use_force=(force == "y"))
    elif action == "4":
        mongodb.recover_mongodb_data_from_pvc("./tools/backup")
