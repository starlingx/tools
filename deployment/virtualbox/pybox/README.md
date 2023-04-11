# Pybox

This automated installer provides you with an easy way to install
StarlingX in many different configuration options. The following 
acronyms are important to understand:

- `AIO` stands for All-In-One, and it means that a single host might 
be responsible for more than one role.
- `SX` stands for Simplex, and it means there's only one controller node
that the whole installation depends on.
- `DX` stands for Duplex, and it means that 2 or more controllers will
be arranged in a high-availability setup.

The configurations available from this script, via the `--setup-type` 
parameter, are:

- `AIO-SX` or "All-In-One Simplex" will set up one single VM that will be both
a controller and a worker nodes.
- `AIO-DX` or "All-In-One Duplex" will set up two controller VMs with one of
them also being a worker.
- `Standard` and `Storage` setups are currently under review.

Overall Design of the Code
--------------------------

The main concepts of the autoinstaller are stages and chains. A stage
is an atomic set of actions taken by the autoinstaller. A chain is a set
of stages executed in a specific order. Stages can be executed
independently and repeated as many times the user needs. Chains can be
configured with the desired stages by the user. Or, the user can select a
specific chain from the available ones.

Example stages:

- create-lab           # Create VMs in vbox: controller-0, controller-1...
- install-controller-0 # Install controller-0 from --iso-location
- config-controller    # Run config controller using the
- config-controller-ini updated based on --ini-* options.
- rsync-config         # Rsync all files from --config-files-dir and
                         --config-files-dir* to /home/sysadmin.
- lab-setup1           # Run lab_setup with one or more --lab-setup-conf
                         files from controller-0.
- unlock-controller-0  # Unlock controller-0 and wait for it to reboot.
- lab-setup2           # Run lab_setup with one or more --lab-setup-conf
                         files from controller-0.

Example chains: [create-lab, install-controller-0, config-controller,
rsync-config, lab-setup1, unlock-controller-0, lab-setup2]. This chain
will install an AIO-SX.

The autoinstaller has a predefined set of chains. The user can select from
these chains and choose from which stage to which stage to do the install.
For example, if the user already executed config_controller, they can choose
to continue from rsync-config to lab-setup2.

The user can also create a custom set of chains, as he sees fit by
specifying them in the desired order. This allows better customization of
the install process. For example, the user might want to execute his own
script after config_controller.  In this case, he will have to specify a
chain like this: [create-lab, install-controller-0, config-controller,
rsync-config, custom-script1, lab-setup1, unlock-controller-0, lab-setup2]

The installer supports creating virtualbox snapshots after each stage so
the user does not need to reinstall from scratch. The user can restore the
snapshot of the previous stage, whether to retry or fix the issue
manually, then continue the process.

## List of Features

Basic:
- Multi-user, and multiple lab installs can run at the same time.
- Uses config_controller ini and lab_setup.sh script to drive the
  configuration [therefore their requirements have to be met prior to
  execution].
- Specify setup (lab) name - this will group all nodes related to
  this lab in a virtual box group
- Setup type - specify what you want to install (SX,DX,Standard,
  Storage)
- Specify start and end stages or a custom list of stages
- Specify your custom ISO, config_controller ini file locations
- Updates config_controller ini automatically with your custom OAM
  networking options so that you don't need to update the ini file for
  each setup
- Rsync entire content from a couple of folders on your disk
  directly on the controller /home/wrsroot thus allowing you easy access
  to your scripts and files
- Take snapshots after each stage

Configuration:
- Specify the number of nodes you want for your setup (one or two controllers,
  x storages, y workers)
- Specify the number of disks attached to each node. They use the
  default sizes configured) or you can explicitly specify the sizes of the
  disks
- Use either 'hostonly' adapter or 'NAT' interface with automated
  port forwarding for SSH ports.

Advanced chains:
- Specify custom chain using any of the existing stages
- Ability to run your own custom scripts during the install process
- Ability to define what scripts are executed during custom script
  stages, their timeout, are executed over ssh or serial, are executed as
  normal user or as root.

Other features
- Log files per lab and date.
- Enable hostiocache option for virtualbox VMs storage controllers
  to speed up install
- Basic support for Kubernetes (AIO-SX installable through a custom
  chain)
- Support to install lowlatency and securityprofile

## Installation and Usage

This section covers a basic functioning example of the **All-In-One Simplex
(AIO-SX) installation**, which creates one VM that will work as both a 
Controller and a Worker. A NAT Network between the host and the Virtual Machine
will be configured and used.

>_NOTE_: the following steps assume you're on a Debian-based Linux box.

1. Install dependencies:

    ```shell
    sudo apt install virtualbox socat git rsync sshpass openssh-client python3-pip python3-venv
    ```

2. Create a NAT Network with the `VBoxManage` CLI that is installed with VirtualBox:

    ```shell
    VBoxManage natnetwork add --netname NatNetwork --network 10.10.10.0/24 --dhcp off --ipv6 on
    VBoxManage natnetwork modify --netname NatNetwork --port-forward-4 http-8080:tcp:[]:8080:[10.10.10.3]:8080
    ```

3. Checkout the repository, and set up Python's Virtual Environment with:

    ```shell
    git clone https://opendev.org/starlingx/tools.git
    cd tools/deployment/virtualbox/pybox
    python3 -m venv venv
    source ./venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

4. Grab the latest ISO (this script was last tested with version 8.0.0):

    ```shell
    wget https://mirror.starlingx.cengn.ca/mirror/starlingx/release/latest_release/debian/monolithic/outputs/iso/starlingx-intel-x86-64-cd.iso \
      -O $HOME/Downloads/stx-8.iso
    ```

5. Now you're ready to run the script. From the `/deployment/virtualbox/pybox`
folder, do:

    ```shell
    python3 ./install_vbox.py --setup-type AIO-SX \
      --iso-location "$HOME/Downloads/stx-8.iso" \
      --labname StarlingX --install-mode serial \
      --config-files-dir ./configs/aio-sx/ \
      --config-controller-ini ./configs/aio-sx/stx_config.ini_centos \
      --ansible-controller-config ./configs/aio-sx/localhost.yml \
      --vboxnet-type nat \
      --vboxnet-name NatNetwork \
      --nat-controller0-local-ssh-port 3122 \
      --controller0-ip 10.10.10.3 \
      --ini-oam-cidr '10.10.10.0/24' \
      --snapshot
    ```

The script takes a while to do all the things (from creating a VM and 
installing an OS in it to configuring StarlingX). Several restarts might
occur, and you might see a VirtualBox with a prompt. You don't need to type 
anything. While the installation script is running it will take care of 
everything for you.
