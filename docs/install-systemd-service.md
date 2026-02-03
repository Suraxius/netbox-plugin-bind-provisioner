1. Create System Unit file
    ```
    cat <<EOF > /etc/systemd/system/netbox-bind-endpoint.service
    [Unit]
    Description=Netbox BIND Catalog Endpoing
    Documentation=https://github.com/Suraxius/netbox-plugin-bind-provisioner
    After=network-online.target
    Wants=network-online.target
    
    [Service]
    Type=simple
    
    User=netbox
    Group=netbox
    PIDFile=/var/tmp/netbox.pid
    WorkingDirectory=/opt/netbox
    
    ExecStart=/opt/netbox/venv/bin/python3  /opt/netbox/netbox/manage.py dns-transfer-endpoint --port 5354
    
    Restart=on-failure
    RestartSec=30
    PrivateTmp=true
    
    [Install]
    WantedBy=multi-user.target
    EOF
    ```

2. Enable and start the service
    ```
    systemctl enable netbox-bind-endpoint
    systemctl start netbox-bind-endpoint
    systemctl status netbox-bind-endpoint
    ```
