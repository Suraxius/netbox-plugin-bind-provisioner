# Netbox Bind Provisioner
A NetBox plugin that implements a lightweight DNS server to automate the
provisioning and configuration of a BIND9 server based on DNS records
maintained in NetBox. (netbox-plugin-dns).

## Plugin configuration
The plugin has been reworked: instead of exporting zone files, it now provides
a minimal DNS server that is fed directly from NetBox’s DNS data. This server
also exposes specialized catalog zones that BIND uses to automatically discover
newly created zones and remove deleted ones. The plugin supports BIND views and
basic DNS security via TSIG.

The plugin exposes one catalog zone per view. Each catalog zone is available
under the special zone name **"catz"** and can be queried through the built-in
DNS server like any other zone.

For proper operation, each view requires an installed TSIG key, and the
`bind-transfer-endpoint` must be running as a separate background service using
the `manage.py` command. Note that DNSSEC support will be added once BIND9
provides a mechanism to configure it through the Catalog Zones system.

To start the service:
```
manage.py bind-transfer-endpoint --port 5354
```

When configuring the plugin, you need to provide a path on the filesystem for
this file where the plugin can create and manage it. Please do not update it by
hand or remove it unless you know what you are doing.

### Service parameters
Parameter | Description
--------- | -------------------------------------------------------------------
--port    | Port to listen on for requests (defaults to 5354)
--address | IP of interface to bind to (defaults to 0.0.0.0)

### Plugin settings
Setting             | Description
--------------------| ---------------------------------------------------------
catalog_serial_file | !!!NO LONGER USED!!! Replaced by DB entry.
tsig_keys           | Maps a TSIG Key to be used for each view.

## Installation guide
This setup provisions a BIND9 server directly with DNS data from NetBox.
BIND9 can optionally run on a separate server. If so, any reference to
127.0.0.1 in step 6 must be replaced with the IP address of the NetBox host.
TCP and UDP traffic from the BIND9 server to the NetBox host must be allowed on
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
    echo netbox-plugin-bind-provisioner >> local_requirements.txt
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
    PLUGINS = ['netbox_dns', 'netbox_plugin_bind_provisioner']
    ```

    Configure the Bind Exporter Plugin using the PLUGINS_CONFIG dictionary.
    Change
    ```
    PLUGINS_CONFIG = {}
    ```
    to
    ```
    PLUGINS_CONFIG = {
        "netbox_plugin_bind_provisioner": {
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
    PLUGINS_CONFIG.netbox_plugin_bind_provisioner.tsig_keys.<dns_view_name>
    ```
    This allows the plugin to map requests to the right dns view using the tsig
    signature from each request.

4. Run migrations
    ```
    python3 netbox/manage.py migrate
    ```

5. Start listener
    This step runs the DNS endpoint used by bind to configure itself. You may want
    to write a service wrapper that runs this in the background.
    A guide for setting up a systemd service on Ubuntu is provided by Matt
    Kollross [here](docs/install-systemd-service.md). Dont forget to activate
    the venv if you do decide to run this service in the background.

    Note that `--port 5354` is optional. The listener will bind this port
    by default.
    ```
    python3 netbox/manage.py bind-transfer-endpoint --port 5354
    ```

6. Configuring a Bind9 to interact with Netbox via the bind-transfer-endpoint
   endpoint. Note that its not possible to give all the correct details of the
   `options` block as it is heavily dependent on the Operating System used.
   Please dont forget to adjust as required.
   
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

    ########## ZONES ##########

    view "public" {
        key "public_view_key" {
            algorithm hmac-sha256;
            secret "base64-encoded-secret";
        };

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
        key "private_view_key" {
            algorithm hmac-sha256;
            secret "base64-encoded-secret";
        };

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

