# Netbox DNS Bridge
(Formerly Netbox Bind Provisioner)

The NetBox DNS Bridge plugin extends [NetBox DNS](https://github.com/sys4/netbox-plugin-dns) by
embedding a lightweight DNS server directly within NetBox. It acts as a bridge between NetBox DNS
and your existing DNS infrastructure, leveraging native DNS mechanisms for seamless integration.
These include zone transfers (RFC 5936), catalog zones (RFC 9432), and dynamic updates (RFC 2136).

<a href="https://pypi.org/project/netbox-plugin-dns-bridge/"><img src="https://img.shields.io/pypi/v/netbox-plugin-dns-bridge" alt="PyPi"></a>
<a href="https://github.com/suraxius/netbox-plugin-dns-bridge/stargazers"><img src="https://img.shields.io/github/stars/suraxius/netbox-plugin-dns-bridge?style=flat" alt="Stars Badge"></a>
<a href="https://github.com/suraxius/netbox-plugin-dns-bridge/network/members"><img src="https://img.shields.io/github/forks/suraxius/netbox-plugin-dns-bridge?style=flat" alt="Forks Badge"></a>
<a href="https://github.com/suraxius/netbox-plugin-dns-bridge/issues"><img src="https://img.shields.io/github/issues/suraxius/netbox-plugin-dns-bridge" alt="Issues Badge"></a>
<a href="https://github.com/suraxius/netbox-plugin-dns-bridge/pulls"><img src="https://img.shields.io/github/issues-pr/suraxius/netbox-plugin-dns-bridge" alt="Pull Requests Badge"></a>
<a href="https://github.com/suraxius/netbox-plugin-dns-bridge/graphs/contributors"><img src="https://img.shields.io/github/contributors/suraxius/netbox-plugin-dns-bridge?color=2b9348" alt="GitHub contributors"></a>
<a href="https://github.com/suraxius/netbox-plugin-dns-bridge/blob/master/LICENSE"><img src="https://img.shields.io/github/license/suraxius/netbox-plugin-dns-bridge?color=2b9348" alt="License Badge"></a>
<a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code Style Black"></a>
<a href="https://pepy.tech/project/netbox-plugin-dns-bridge"><img src="https://static.pepy.tech/personalized-badge/netbox-plugin-dns-bridge?period=total&left_color=BLACK&right_color=BLUE&left_text=Downloads" alt="Downloads"></a>
<a href="https://pepy.tech/project/netbox-plugin-dns-bridge"><img src="https://static.pepy.tech/personalized-badge/netbox-plugin-dns-bridge?period=monthly&left_color=BLACK&right_color=BLUE&left_text=Downloads%2fMonth" alt="Downloads/Month"></a>
<a href="https://pepy.tech/project/netbox-plugin-dns-bridge"><img src="https://static.pepy.tech/personalized-badge/netbox-plugin-dns-bridge?period=weekly&left_color=BLACK&right_color=BLUE&left_text=Downloads%2fWeek" alt="Downloads/Week"></a>



![Architecture Overview](docs/architecture-overview.svg)

DISCLAIMER: The dynamic update endpoint isn't here yet. Its planned - without a deadline.

## Plugin configuration
While providing Zone transfers via AXFR, the Server also exposes specialized catalog zones that BIND
and other RFC9432 compliant DNS Servers use to automatically discover newly created zones and remove
deleted ones. The plugin supports views and basic DNS security via TSIG.

The plugin exposes one catalog zone per view. Each catalog zone is made available under the special
zone name **"catz"** and addtionally under **"[viewname].catz"** and may be queried through the
built-in DNS server just like any other dns zone.

For proper operation, each view requires an installed TSIG key, and the `dns-transfer-endpoint` must
be running as a separate background service using the `manage.py` command. Note that DNSSEC support
will be added once BIND9 provides a mechanism to configure it through the Catalog Zones system.

To start the transfer endpoint service in the foreground:
```
manage.py dns-transfer-endpoint --port 5354
```
This process needs to be scheduled as a background service for the built-in DNS Server to work
correctly. For Linux users with Systemd (Ubuntu, etc), Matt Kollross provides a startup unit and
instructions [here](docs/install-systemd-service.md).

### Service parameters
Parameter | Description
--------- | -------------------------------------------------------------------
--port    | Port to listen on for requests (defaults to 5354)
--address | IP of interface to bind to (defaults to 0.0.0.0)

### Plugin settings
Setting             | Description
--------------------| ---------------------------------------------------------
tsig_keys           | Maps a TSIG Key to be used for each view.

## Plugin compatibility
This plugin is an extension to the netbox-plugin-dns plugin. As such the versioning of this plugin
was changed to match the one of the netbox-plugin-dns plugin closely. To guarantee compatability,
ensure that the major and minor version match between both plugins.
For example, when using netbox-plugin-dns `v1.5.5` install netbox-plugin-dns-bridge `v1.5.x`.

## Post 1.0.7 Upgrade Guide
Applies only if you have a <= 1.0.7 installation. If you are freshly installing this plugin,
go on to [Installation Guide](#installation-guide).

After version 1.0.7, the project was restructured and renamed. Until that point version updates
happened more or less automatically. However, this shift is more of a move from one plugin to
another as the package name has changed.

This should not be an issue since the slave DNS Servers connected to Netbox can operate
independently while this plugin is being upgraded.

Make sure to note down the catalog zone serial number before going further.

1. Remove Netbox Bind Provisioner package
    - Remove `netbox-plugin-bind-provisioner` from **local_dependencies.txt**
    - Uninstall the package: `pip uninstall netbox-plugin-bind-provisioner`
2. Install Netbox DNS Bridge package
    - Install the package `pip install netbox-plugin-dns-bridge`
    - Put `netbox-plugin-dns-bridge` in your **local_dependencies.txt** so it will be installed on
      next upgrade.
3. Adjust your `configuration.py`
    - Change the plugin name from `netbox-plugin-bind-provisioner` to `netbox-plugin-dns-bridge`
    - Change the key in `PLUGIN_CONFIG` from `netbox_plugin_bind_provisioner` to `netbox_dns_bridge`
4. Run migrations: `manage.py migrate`
5. Restore the catalog zone serial you noted down previously so that your slave dns servers continue
   to pull the changes: `manage.py dns-settings set catalog-zone-soa-serial yourserialnumber`
6. Start the `dns-transfer-endpoint` service.
7. Mission accomplished.

## Installation guide
This setup provisions a BIND9 server directly with DNS data from NetBox. BIND9 can optionally run on
a separate server. If so, any reference to 127.0.0.1 in step 6 must be replaced with the IP address
of the NetBox host. TCP and UDP traffic from the BIND9 server to the NetBox host must be allowed on
port 5354 (or the port you have configured).

This guide assumes:
- Netbox has been installed under /opt/netbox
- Bind9 is installed on the same host as Netbox
- The Netbox DNS Plugin netbox-plugin-dns is installed
- The following dns views exist in Netbox DNS:
    - `public` (the default)
    - `private`

1. Preliminaries
    - Install Bind9 on the same host that netbox is on.
    - Generate a TSIG Key for the `public` and `private` dns views respectively.

2. Adding required package
    ```
    cd netbox
    echo netbox-plugin-dns-bridge >> local_requirements.txt
    . venv/bin/activate
    pip install -r local_requirements.txt
    ```

3. Updating netbox plugin configuration (configuration.py)
    Change following line from
    ```
    PLUGINS = ['netbox_dns']
    ```
    to
    ```
    PLUGINS = ['netbox_dns', 'netbox_dns_bridge']
    ```

    Configure the DNS Bridge Plugin using the PLUGINS_CONFIG dictionary.
    Change
    ```
    PLUGINS_CONFIG = {}
    ```
    to
    ```
    PLUGINS_CONFIG = {
        "netbox_dns_bridge": {
            "tsig_keys": {
                "public": {
                    "keyname":   "public_view_key",
                    "algorithm": "hmac-sha256",
                    "secret":    "base64-encoded-secret"
                },
                "private": {
                    "keyname":   "private_view_key",
                    "algorithm": "hmac-sha256",
                    "secret":    "base64-encoded-secret"
                }
            }
        }
    }
    ```
    Note that the tsig-key attributes keyname, algorithm and secret form a
    dictionary in following python structure path:
    ```
    PLUGINS_CONFIG.netbox_dns_bridge.tsig_keys.<dns_view_name>
    ```
    This allows the plugin to map requests to the right dns view using the tsig
    signature from each request.

4. Run migrations
    ```
    manage.py migrate
    ```

5. Start listener

    This step runs the DNS endpoint used by bind to configure itself. You may want to write a
    service wrapper that runs this in the background. A guide for setting up a systemd service on
    Ubuntu is provided by Matt Kollross [here](docs/install-systemd-service.md). Dont forget to
    activate the venv if you do decide to run this service in the background.

    Note that `--port 5354` is optional. The listener will bind this port by default.
    ```
    manage.py dns-transfer-endpoint --port 5354
    ```

6. Configuring a Bind9 to interact with Netbox via the dns-transfer-endpoint endpoint. Note that its
    not possible to give all the correct details of the `options` block as it is heavily dependent
    on the Operating System used. Please dont forget to adjust as required.
   
    ```
    ########## OPTIONS ##########

    options {
        allow-update      { none; };
        allow-query       { any; };
        allow-recursion   { none; };
        notify            yes;
        min-refresh-time  60;
    };

    ########## ACLs ##########

    acl public {
        !10.0.0.0/8;
        !172.16.0.0/12;
        !192.168.0.0/16;
        any;
    };

    acl private {
        10.0.0.0/8;
        172.16.0.0/12;
        192.168.0.0/16;
    };

    ######## TSIG Keys ########
        key "public_view_key" {
            algorithm hmac-sha256;
            secret "base64-encoded-secret";
        };

        key "private_view_key" {
            algorithm hmac-sha256;
            secret "base64-encoded-secret";
        };
    ###########################


    ########## ZONES ##########
    view "public" {
        match-clients { public; };

        catalog-zones {
            zone "catz"
                default-masters { 127.0.0.1 port 5354 key "public_view_key"; }
                zone-directory "/var/lib/bind/zones"
                min-update-interval 1;
        };

        zone "catz" {
            type slave;
            file "/var/lib/bind/zones/catz_public";
            masters { 127.0.0.1 port 5354 key "public_view_key"; };
            notify no;
        };
    };

    view "private" {
        match-clients { private; };

        catalog-zones {
            zone "catz"
                default-masters { 127.0.0.1 port 5354 key "private_view_key"; }
                zone-directory "/var/lib/bind/zones"
                min-update-interval 1;
        };

        zone "catz" {
            type slave;
            file "/var/lib/bind/zones/catz_private";
            masters { 127.0.0.1 port 5354 key "private_view_key"; };
            notify no;
        };
    };
    ```

7. Restart bind - Done


