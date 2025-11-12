# Netbox Bind Provisioner
A Netbox Plugin that provides a minimal DNS Server for the automatic
provisioning of a Bind9 Server from Netbox DNS data (netbox-plugin-dns).

## Plugin configuration
The plugin was re-worked; Instead of exporting zone files, it provides an
entire (though minimal) DNS Server that is fed directly from Netbox's DNS data.
The Server also provides specialized "catalog" zones that bind uses to
automatically discover new zones and remove deleted ones. The plugin supports
view as well as basic dns security using TSIG.

To work correctly, each view needs a tsig key installed and the
bind-transfer-endpoint needs to be running as its own service in the background
via the `manage.py` command. Note that dnssec support will be implemented as
soon as bind9 has a mechanism to allow configuration of such via the Catalog
Zones mechanism.

```
manage.py bind-transfer-endpoint --port 5354
```

The plugin also currently needs a file that tracks the current state of the
catalog zone's SOA serial. The serial represents the catalog zone's SOA record
serial number and is used by downstream DNS Servers to determine if the catalog
zone was updated (e.g. if a zone is added/modified/removed from netbox).
The file is used to persist the SOA record's serial across service restarts.
It will be replaced by a database entry once the plugin has its own models.

### Service parameters
Parameter | Description
--------- | -------------------------------------------------------------------
--port    | Port to listen on for requests (defaults to 5354)
--address | IP of interface to bind to (defaults to 0.0.0.0)

### Plugin settings
Setting             | Description
--------------------| ---------------------------------------------------------
catalog_serial_file | The catalog serial counter. The file needs to be writable.
tsig_keys           | Maps a TSIG Key to be used for each view.

### Plugin example configuration
```
PLUGINS_CONFIG = {
    "netbox_bind_provisioner": {
        "catalog_serial_file": "/opt/netbox/catalog-serial.txt",
        "tsig_keys": {
            "key1name": {
                "view":      "public",
                "keyname":   "view1key",
                "algorithm": "hmac-sha256",
                "secret":    "base64-encoded-secret"
            },
            "key2name": {
                "view":      "private",
                "keyname":   "view2key",
                "algorithm": "hmac-sha256",
                "secret":    "base64-encoded-secret"
            }
        },
    }
}
```

## Bind example configuration
```
options {
    ...
    ...
    allow-update      { none; };
    allow-query       { any; };
    allow-recursion   { none; };
    notify            yes;
    min-refresh-time 60;
    ...
    ...
};

# ACLs

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

# Zone definitions

view "public" {
    key "key1name" {
        algorithm hmac-sha256;
        secret "base64-encoded-secret";
    };

    match-clients { public; };

    catalog-zones {
        zone "catz"
            default-masters { 127.0.0.1 port 5354 key "key1name"; }
            zone-directory "/var/lib/bind/zones"
            min-update-interval 1;
    };

    zone "catz" {
        type slave;
        file "/var/lib/bind/zones/catz_public";
        masters { 127.0.0.1 port 5354 key "key1name"; };
        notify no;
    };
};

view "private" {
    key "key2name" {
        algorithm hmac-sha256;
        secret "base64-encoded-secret";
    };

    match-clients { private; };

    catalog-zones {
        zone "catz"
            default-masters { 127.0.0.1 port 5354 key "key2name"; }
            zone-directory "/var/lib/bind/zones"
            min-update-interval 1;
    };

    zone "catz" {
        type slave;
        file "/var/lib/bind/zones/catz_private";
        masters { 127.0.0.1 port 5354 key "key2name"; };
        notify no;
    };
};
```

