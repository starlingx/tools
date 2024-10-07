#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import subprocess
from typing import Optional

from stx import utils

logger = logging.getLogger('MinikubeCtl')
utils.set_logger(logger)


def run_command(cmd: list, timeout: int = 30) -> Optional[str]:
    """
    Executes a subprocess command and returns the stdout as a string.

    Args:
        cmd (list): The command to be executed as a list of arguments.
        timeout (int): Maximum time to wait for the command to complete, in seconds. Default is 30 seconds.

    Returns:
        str: The stdout output of the command if successful.
        None: If the command fails or times out.

    Raises:
        subprocess.TimeoutExpired: If the command exceeds the specified timeout.
        subprocess.CalledProcessError: If the command exits with a non-zero status.
    """
    logger.info(f"Executing command: {' '.join(cmd)} with a timeout of {timeout} seconds")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="UTF-8",
            check=True,
            timeout=timeout
        )
        return result.stdout.strip()

    except subprocess.CalledProcessError:
        return None

    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")
        return None

    except Exception as e:
        logger.error(f"An unexpected error occurred while running the command: {e}")
        return None


class MinikubeCtl(object):
    """A controller class for managing Minikube profiles."""

    def __init__(
            self, bin_path: str = "minikube",
            profile_name: str = "",
    ):
        if not bin_path.endswith("minikube"):
            raise Exception(f"Invalid binary path for minikube command: {bin_path}")
        self.bin_path = bin_path
        self.minikube_profile = profile_name

    def exists(self) -> bool:
        """
        Check if the given profile name exists in the list of profiles.

        This method fetches the list of valid Minikube profiles and checks
        if the profile with the name provided during initialization exists.

        Returns:
            bool: True if the profile exists, False otherwise.

        Raises:
            Exception: If an error occurs while fetching the profile list.
        """
        try:
            profiles = self.__get_profiles()
            if not profiles:
                logger.warning("No profiles found or failed to retrieve profiles.")
                return False

            profile_exists = self.minikube_profile in profiles
            if profile_exists:
                logger.info(f"Profile '{self.minikube_profile}' exists.")
            else:
                logger.error(f"Profile '{self.minikube_profile}' does not exist.")
            return profile_exists

        except Exception as e:
            logger.error(f"An error occurred while checking if profile exists: {e}", str(e))
            return False

    def is_started(self) -> bool:
        """
        Check if the Minikube profile is started by checking its status.

        This method runs the 'minikube status' command for the specified profile and
        returns True if all key services (such as Kubelet, APIServer, etc.) are in
        the "Running" state. It processes the JSON output from the command to make
        this determination.

        Returns:
            bool: True if the Minikube profile is running (all services are "Running").
                  False otherwise.

        Raises:
            Exception: If an error occurs while executing the command or parsing the output.
        """
        if not self.exists():
            raise MinikubeProfileNotFoundError(self.minikube_profile)

        cmd = [self.bin_path, "status", "-p", self.minikube_profile, "-o", "json"]
        logger.info(f"Checking status of Minikube profile '{self.minikube_profile}' with command: {' '.join(cmd)}")

        output = run_command(cmd)

        try:
            if not output:
                return False
            try:
                json_output = json.loads(output)

                logger.debug(
                    f"Minikube status output for profile '{self.minikube_profile}': \n{json_output}"
                )

                for service_name, service_info in json_output.items():
                    if isinstance(service_info, dict) and service_info.get("Status") != "Running":
                        logger.info(
                            f"Service '{service_name}' is not running for profile '{self.minikube_profile}'."
                        )
                        return False
                return True

            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse JSON output for profile '{self.minikube_profile}': {e}"
                )
                return False

        except subprocess.CalledProcessError as e:
            logger.error(
                f"Minikube command failed while checking profile status: {e}"
            )
            return False

        except Exception as e:
            logger.error(
                f"An unexpected error occurred while checking profile status: {e}"
            )
            return False

    def start(self):
        """
        Starts the Minikube profile if it's not already started.

        This method starts the Minikube profile using the 'minikube start' command.
        """

        if self.is_started():
            logger.info(f"Profile '{self.minikube_profile}' is already running.")
            return

        logger.info(f"Starting Minikube profile '{self.minikube_profile}'")
        cmd = [self.bin_path, "start", "-p", self.minikube_profile]

        output = run_command(cmd, 120)
        if output:
            logger.info(f"Minikube profile '{self.minikube_profile}' started successfully.")
        else:
            raise Exception(f"Failed to start Minikube profile '{self.minikube_profile}'.")

    def __get_profiles(self) -> list:
        """
        Fetches the list of Minikube profiles.

        This method executes the 'minikube profile list' command and retrieves
        the profiles in JSON format. It extracts the valid profile names from the output.

        Returns:
            list: A list of profile names if successful, or an empty list if no profiles are found
                  or if an error occurs during the execution.

        Raises:
            Exception: If an error occurs during command execution or JSON parsing.
        """
        cmd = [self.bin_path, "profile", "list", "-l", "-o", "json"]
        logger.info(f"Fetching Minikube profiles with command: {' '.join(cmd)}")

        try:
            output = run_command(cmd)
            if not output:
                logger.warning("No output received from Minikube command.")
                return []

            try:
                profiles_data = json.loads(output)
                valid_profiles = profiles_data.get("valid", [])
                if not valid_profiles:
                    logger.warning("No valid profiles found.")
                    return []

                profile_names = [profile["Name"] for profile in valid_profiles]
                logger.info(f"Found profiles: {profile_names}")
                return profile_names

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON output from Minikube: {e}")
                return []

        except subprocess.CalledProcessError as e:
            logger.error(f"Minikube command failed: {e}")
            return []

        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []


class MinikubeProfileNotFoundError(Exception):
    """Exception raised when a Minikube profile is not found."""

    def __init__(self, profile_name):
        self.profile_name = profile_name
        super().__init__(
            f"Profile '{profile_name}' not found. Run: ./stx-init-env"
        )


class MinikubeProfileNotRunning(Exception):
    """Exception raised when a Minikube profile is not running."""

    def __init__(self, profile_name):
        self.profile_name = profile_name
        super().__init__(
            f"Profile '{profile_name}' not running. Run: stx control start --wait"
        )
