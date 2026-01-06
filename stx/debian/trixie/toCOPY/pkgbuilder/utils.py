import os
import shutil
import subprocess

logger = None


def set_logger(log):
    global logger
    logger = log


def is_tmpfs(mount_point):
    #  Check if the given mount point is a tmpfs filesystem.
    try:
        # Run the 'mount' command to get filesystem details
        result = subprocess.run(['mount', '-v'], capture_output=True, text=True, check=True)
        # Check if the mount point is listed as tmpfs
        for line in result.stdout.splitlines():
            if mount_point in line and 'tmpfs' in line:
                return True
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check filesystem type: {e}")
        return False


def is_directory_empty(directory):
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"The path {directory} is not a directory or does not exist.")
    return not any(os.scandir(directory))


def unmount_tmpfs(mount_point):
    # Unmount the tmpfs
    if not is_tmpfs(mount_point):
        return False
    try:
        subprocess.run(['umount', mount_point], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to unmount {mount_point}: {e}")
        return False
    logger.debug(f"Unmounted {mount_point}")


def clear_directory(directory):
    # Empty the directory without actually deleting it.
    # The intended use is for mount points.
    if not is_directory_empty(directory):
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
