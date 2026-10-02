# Network-NINJA

**Turn unused network space into a **curity detection surface through intentional network design.**

Network-NINJA is an open-source, distributed network sensor designed to detect unexpected traffic inside enterprise networks.

It combines:

- Existing routers and Layer 3 switches
- Intentional routing design
- Lightweight distributed sensors
- Centralized configuration and monitoring

Network-NINJA itself does not configure or control routing.

Network administrators define monitored network ranges and configure the existing routing infrastructure to direct traffic for those ranges toward Network-NINJA sensors.

The sensors observe selected traffic and send detection events to the Network-NINJA Manager.

This approach makes security monitoring part of the network design process.

> Network-NINJA does not replace network design.  
> It encourages organizations to understand their networks deeply enough to design security into them.

README_ja.md


---

## Overview

Many organizations operate large, segmented networks across offices, data centers, branches, stores, and other locations.

Some network ranges are actively used, while others are unused, reserved, or intentionally excluded from normal business communication.

Traffic directed toward those unused or monitored ranges can provide a valuable security signal.

For example, such traffic may be associated with:

- Network reconnaissance
- Internal network scanning
- Misconfiguration
- Unauthorized access attempts
- Malware activity
- Suspicious lateral movement

Network-NINJA allows organizations to place lightweight sensors throughout their network and centrally manage the traffic those sensors monitor.

```text
                  Enterprise Network
                          |
                          v
                 Router / L3 Switch
                          |
                 Routing configured
                by network operators
                          |
                          v
                Network-NINJA Agent
                    Network Sensor
                          |
                 Detection via Syslog
                          |
                          v
               Network-NINJA Manager
                          |
              +-----------+-----------+
              |                       |
            Web UI                  SQLite
```

---

## Core Concept

The core idea behind Network-NINJA is simple:

> **Traffic going to a network where legitimate communication is not expected deserves attention.**

Network administrators identify network ranges that should not normally receive traffic.

They then configure their routers or Layer 3 switches so that traffic destined for those ranges reaches a Network-NINJA sensor.

The Network-NINJA Agent monitors the received traffic according to its centrally managed configuration.

When matching traffic is detected, the Agent generates a Syslog event and sends it to the configured Syslog destination.

```text
1. Identify an unused or monitored network range
                         |
                         v
2. Design the required routing
                         |
                         v
3. Configure a router or Layer 3 switch
                         |
                         v
4. Direct relevant traffic to a Network-NINJA Agent
                         |
                         v
5. Monitor selected protocols and ports
                         |
                         v
6. Generate and collect detection events
```

---

## Security by Design

Network-NINJA intentionally separates network design from traffic detection.

### The network infrastructure is responsible for routing

Existing routers and Layer 3 switches determine which traffic reaches each Network-NINJA Agent.

Network-NINJA does not automatically install routes or modify routing tables.

### Network-NINJA is responsible for sensing

The Network-NINJA Agent observes traffic delivered to it and reports matching events.

### Administrators design the detection surface

Administrators decide:

- Which network ranges should be monitored
- Which ranges should not receive legitimate traffic
- Where sensors should be deployed
- How traffic should be routed to each sensor
- Which protocols and ports each sensor should monitor
- Which traffic should be excluded from monitoring

This process requires an understanding of the organization's:

- Network topology
- Address allocation
- Routing architecture
- Segmentation
- Normal communication paths
- Expected operational traffic

For this reason, Network-NINJA is not only a network sensor.

It is an approach for incorporating security monitoring into network architecture from the design stage.

```text
Network Understanding
         +
Routing Design
         +
Distributed Sensors
         +
Centralized Management
         =
Security by Design
```

---

## Architecture

Network-NINJA consists primarily of a **Manager** and one or more **Agents**.

```text
                   +-----------------------+
                   | Network-NINJA Manager |
                   +-----------+-----------+
                               |
                    Management and Control
                               |
              +----------------+----------------+
              |                                 |
              v                                 v
     +-----------------+               +-----------------+
     |     Agent A     |               |     Agent B     |
     | Network Sensor  |               | Network Sensor  |
     +--------+--------+               +--------+--------+
              ^                                 ^
              |                                 |
       Router / L3 Switch                Router / L3 Switch
              ^                                 ^
              |                                 |
       Monitored Traffic                 Monitored Traffic
```

The Manager provides centralized management, while Agents operate as distributed network sensors.

The routing required to deliver monitored traffic to each Agent is configured separately on the organization's routers or Layer 3 switches.

---

## Components

### Manager

The Network-NINJA Manager provides centralized visibility and configuration management.

Current Manager capabilities include:

- Web-based management interface
- REST API
- Agent heartbeat management
- Node status monitoring
- Syslog reception
- Syslog search and retrieval
- Configuration deployment
- SQLite-based data persistence

The Manager listens on the following default ports:

| Service | Default port |
|---|---:|
| Web UI | TCP/8080 |
| REST API | TCP/8080 |
| Syslog receiver | UDP/514 |

A non-privileged Syslog port such as UDP/5514 can be used when the Manager is not running with permission to bind to UDP/514.

### Agent

The Network-NINJA Agent is a lightweight, distributed network sensor.

Each Agent:

- Monitors selected network traffic
- Sends detection events using Syslog
- Sends a heartbeat to the Manager
- Polls the Manager for configuration updates
- Applies centrally distributed monitoring settings
- Reports its node identity and display label

The Agent is designed to run as a container and can be deployed on supported network devices, servers, virtual machines, or other appropriate Linux environments.

### Router or Layer 3 Switch

The router or Layer 3 switch is not part of the Network-NINJA software.

It remains responsible for routing traffic through the enterprise network.

Network administrators configure the router or Layer 3 switch to direct traffic for selected network ranges toward a Network-NINJA Agent.

```text
Corporate network:     10.0.0.0/8
Monitored range:       192.168.0.0/16
Sensor destination:    Network-NINJA Agent
```

This is only a conceptual example. Routing configuration must be designed for the actual network environment.

---

## Traffic Monitoring

Network-NINJA Agents monitor selected traffic based on configuration received from the Manager.

Currently supported traffic types include:

- ICMP Echo Request
- ICMP Echo Reply
- TCP port 80, commonly used for HTTP
- TCP port 443, commonly used for HTTPS
- TCP port 445, commonly used for SMB

When multiple traffic types are enabled, the Agent combines them into a packet-capture filter.

A conceptual example is:

```text
ICMP Echo Request or Reply
or TCP port 80
or TCP port 443
or TCP port 445
```

These protocols and ports can provide visibility into traffic that may be relevant during:

- Network reconnaissance
- Unauthorized service discovery
- Unexpected access attempts
- Malware activity
- Lateral movement
- Communication caused by configuration errors

Network-NINJA does not classify traffic as malicious based solely on a protocol or port number.

TCP ports 80 and 443, for example, are also widely used for legitimate HTTP and HTTPS communication.

The security value comes from the combination of:

- Where the traffic was observed
- Whether legitimate communication was expected
- Which source generated the traffic
- Which monitored range was accessed
- Which protocol or port was used
- The surrounding operational context

Traffic reaching a deliberately monitored, normally unused network range can therefore provide a stronger signal than the port number alone.

---

## Example Detection Scenario

Assume an organization primarily uses the following private address space:

```text
10.0.0.0/8
```

The organization decides that a selected range is not used for legitimate business communication and should instead become a monitored detection surface.

A network administrator configures a route toward a Network-NINJA Agent.

```text
Workstation or compromised host
              |
              | Unexpected traffic
              v
       Router / L3 Switch
              |
              | Administrator-defined route
              v
     Network-NINJA Agent
              |
              | Matching traffic detected
              v
          Syslog event
              |
              v
     Network-NINJA Manager
```

If a host performs broad reconnaissance and sends ICMP, HTTP, HTTPS, or SMB traffic toward the monitored range, the Agent can observe matching traffic and generate an event.

The monitored network range acts as a detection surface, while the Agent acts as the sensor.

---

## Detection, Not Blocking

Network-NINJA focuses on detection and visibility.

It is not designed to operate as:

- A firewall
- An intrusion prevention system
- A replacement for access control
- An automated routing controller
- A malware classification engine

Network-NINJA observes selected traffic and provides information that defenders can investigate.

Blocking, isolation, remediation, and incident response should be handled by the organization's existing security and network controls.

---

## Distributed Deployment

Network-NINJA is designed for environments containing multiple network locations.

Potential deployment locations include:

- Headquarters
- Data centers
- Branch offices
- Stores
- Remote sites
- Network aggregation points
- Supported network devices with container capabilities

Each location can host a Network-NINJA Agent.

```text
                +-----------------------+
                | Network-NINJA Manager |
                +-----------+-----------+
                            |
          +-----------------+-----------------+
          |                 |                 |
          v                 v                 v
     HQ Agent          Branch Agent       Store Agent
          ^                 ^                 ^
          |                 |                 |
       HQ Router        Branch Router      Store Router
```

Agents periodically report their status to the Manager, allowing distributed sensors to be monitored centrally.

---

## Features

### Implemented capabilities

- Distributed Manager and Agent architecture
- Configurable packet monitoring
- ICMP Echo Request and Reply monitoring
- TCP/80 monitoring
- TCP/443 monitoring
- TCP/445 monitoring
- Syslog event forwarding
- Central Syslog reception and storage
- Agent heartbeat monitoring
- Online and offline node status
- Centralized configuration deployment
- Periodic Agent configuration polling
- REST API
- Web-based management interface
- SQLite-based persistence
- Docker-based deployment
- Host networking and macvlan deployment options

### Design principles

- Lightweight sensor deployment
- Use of existing network infrastructure
- Separation of routing and sensing responsibilities
- Detection rather than blocking
- Distributed monitoring with centralized management
- Security monitoring integrated into network design
- Administrator-controlled detection surfaces

---

## Repository Structure

```text
Network-NINJA/
├── agent/
│   ├── agent.sh
│   ├── Dockerfile
│   └── docker-compose.yml
├── manager/
│   ├── app.py
│   ├── Dockerfile
│   └── docker-compose.yml
├── LICENSE
├── README.md
└── README_ja.md
```

---

## Requirements

The specific requirements depend on the deployment method.

Typical requirements include:

### Manager

- Linux environment
- Docker and Docker Compose, or Python with Flask
- Network access from Agents
- Permission to receive Syslog traffic
- Persistent storage for the SQLite database

### Agent

- Linux environment
- Docker
- Packet-capture permissions
- Network connectivity to the Manager
- Network connectivity to the configured Syslog destination

The container requires additional networking capabilities:

```text
NET_RAW
NET_ADMIN
```

---

## Starting the Manager

### Docker deployment

Docker Compose is the recommended deployment method.

```bash
cd manager
docker compose up -d
```

Open the Web UI in a browser:

```text
http://<manager-address>:8080
```

### Bare-metal or virtual-machine deployment

Install Flask:

```bash
pip install flask
```

Start the Manager:

```bash
DB_PATH=./ninja.db \
WEB_PORT=8080 \
SYSLOG_PORT=5514 \
python3 app.py
```

Binding to UDP port 514 may require elevated privileges.

When running without those privileges, use a non-privileged port such as:

```bash
SYSLOG_PORT=5514
```

---

## Starting an Agent

### 1. Build the container image

```bash
cd agent
docker build -t ninja-agent .
```

### 2. Start the Agent

```bash
docker run -d \
  --name ninja-agent \
  --restart unless-stopped \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  --network=host \
  -e MANAGER_URL="http://192.168.1.100:8080" \
  -e SYSLOG_SERVER="192.168.1.100" \
  -e SYSLOG_PORT="514" \
  -e NODE_ID="agent-sw01" \
  -e NODE_LABEL="Switch-01 (1F)" \
  ninja-agent
```

Using host networking allows the container to monitor traffic visible through the host's network interfaces.

For environments using a dedicated macvlan network, replace:

```bash
--network=host
```

with:

```bash
--network=<macvlan-network-name>
```

The correct network configuration depends on the host platform and network design.

---

## Environment Variables

| Variable | Required | Description | Example |
|---|---:|---|---|
| `MANAGER_URL` | Yes | URL of the Network-NINJA Manager | `http://192.168.1.100:8080` |
| `SYSLOG_SERVER` | Yes | IP address of the Syslog destination | `192.168.1.100` |
| `SYSLOG_PORT` | No | Syslog destination port, default `514` | `514` |
| `NODE_ID` | No | Unique node identifier, defaults to hostname | `agent-sw01` |
| `NODE_LABEL` | No | Display name shown in the Manager | `Switch-01 (1F)` |

Additional traffic-monitoring options are distributed through the Manager configuration.

---

## Agent Operation

Each Agent performs two periodic management functions:

### Heartbeat

The Agent sends a heartbeat to the Manager every 30 seconds.

The Manager uses the last heartbeat time to determine node status.

| Status | Condition |
|---|---|
| `ONLINE` | Last heartbeat received within two minutes |
| `OFFLINE` | More than two minutes since the last heartbeat |

### Configuration polling

The Agent polls the Manager for configuration updates every 60 seconds.

```text
GET /api/config/<node_id>
```

When a changed configuration is detected, the Agent restarts its monitoring process with the updated settings.

---

## REST API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/heartbeat` | Receive an Agent heartbeat |
| `GET` | `/api/nodes` | Retrieve the node list |
| `DELETE` | `/api/nodes/:id` | Delete a node |
| `GET` | `/api/syslogs` | Retrieve and search Syslog records |
| `GET` | `/api/syslogs/count` | Retrieve the total Syslog record count |
| `POST` | `/api/config/deploy` | Deploy configuration to multiple Agents |
| `GET` | `/api/config/:node_id` | Retrieve configuration for an Agent |

Example query parameters for retrieving Syslog records include:

```text
q=<search-text>
source=<source-address>
limit=<maximum-results>
```

---

## Configuration Deployment

The Manager can distribute configuration to multiple Agents.

Example:

```bash
curl -X POST http://manager:8080/api/config/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "node_ids": [
      "agent-sw01",
      "agent-sw02"
    ],
    "syslog_ip": "192.168.1.200",
    "syslog_port": 514
  }'
```

The deployment flow is:

```text
1. An administrator updates the configuration in the Manager
                         |
                         v
2. The Manager stores the configuration
                         |
                         v
3. Agents periodically poll the Manager
                         |
                         v
4. Each Agent detects the updated configuration
                         |
                         v
5. The Agent restarts monitoring with the new settings
```

---

## Data Persistence

The Manager stores data in SQLite.

The default database path is:

```text
/data/ninja.db
```

The database includes information such as:

| Table | Purpose |
|---|---|
| `nodes` | Node information, last heartbeat time, and configuration |
| `syslogs` | Received Syslog records |
| `config_templates` | Configuration deployment history |

---

## Viewing Agent Logs

```bash
docker logs -f ninja-agent
```

Stop the Agent:

```bash
docker stop ninja-agent
```

Remove the Agent container:

```bash
docker rm ninja-agent
```

---

## Network Design Considerations

Before deploying Network-NINJA, review the following:

- Confirm that the monitored network range is not used by legitimate systems.
- Confirm that routing changes will not interrupt production traffic.
- Identify monitoring, management, and troubleshooting traffic that may require exclusions.
- Determine which sensor should receive traffic for each monitored range.
- Validate return-path behavior where applicable.
- Confirm that the Agent can observe traffic delivered by the network infrastructure.
- Test routing and detection in a controlled environment.
- Document the purpose and ownership of each monitored range.
- Ensure that routing configurations are managed through the organization's normal change-control process.

Network-NINJA does not automatically validate the organization's routing design.

The network administrator remains responsible for ensuring that the design is safe and appropriate for the environment.

---

## Security Considerations

Network-NINJA observes network traffic and may store source addresses, destination addresses, ports, timestamps, and related event information.

Deployments should therefore consider:

- Access control for the Manager
- Protection of the Web UI and REST API
- Protection of Syslog transport
- Database file permissions
- Log retention requirements
- Privacy and organizational policies
- Network configuration change control
- Separation of management and monitored traffic
- Validation of container privileges
- Limiting access to authorized administrators

Do not expose the Manager interface directly to untrusted networks without appropriate protection.

---

## Limitations

Network-NINJA should not be treated as proof that a system is compromised.

A detection event indicates that selected traffic reached a Network-NINJA sensor.

Possible causes include:

- Malicious reconnaissance
- Unauthorized access
- Malware activity
- Operational testing
- Monitoring activity
- User experimentation
- Incorrect routing
- Incorrect application configuration
- Other legitimate or accidental traffic

Events should be investigated together with other information such as endpoint logs, authentication records, firewall logs, DNS logs, flow data, and incident-response telemetry.

---

## Use Cases

### Detection of unexpected network access

Observe traffic directed toward a network where normal communication is not expected.

### Network reconnaissance visibility

Detect selected protocols used by a host while exploring monitored address space.

### Distributed branch monitoring

Deploy lightweight Agents at multiple branches, stores, or remote network locations.

### SMB activity monitoring

Observe TCP/445 traffic reaching deliberately monitored network ranges.

### Security architecture validation

Verify whether network segmentation and expected communication paths behave as designed.

### Security by Design exercises

Use the selection of monitored ranges and sensor locations to improve understanding of the organization's network topology and routing architecture.

### Research and education

Explore routing-based detection surfaces, distributed sensing, and network deception concepts in controlled environments.

---

## Project Status

Network-NINJA is under active development.

Interfaces, configuration formats, monitoring options, and deployment procedures may change as the project evolves.

Review the source code and test the software in a controlled environment before production deployment.

---

## Contributing

Contributions, testing, documentation improvements, and feedback are welcome.

If you find a bug or would like to suggest an improvement, open an Issue in this repository.

When reporting a problem, include:

- Manager or Agent component
- Deployment method
- Relevant configuration
- Expected behavior
- Actual behavior
- Relevant logs with sensitive information removed

---

## License

Network-NINJA is released under the MIT License.

See the LICENSE file for details.

---

## Author

**Ken Sugio**

Cybersecurity and network security researcher and engineer.

Areas of interest include:

- Network security
- Network monitoring
- Network architecture
- Network deception
- Security by Design
- Zero Trust
- Threat detection
- Distributed security sensors

---

## Disclaimer

Network-NINJA is intended for authorized defensive security, research, education, and testing purposes.

Users are responsible for ensuring that deployment, routing configuration, monitoring, data collection, and testing comply with applicable laws, regulations, contracts, and organizational policies.

The authors and contributors are not responsible for damage or disruption caused by incorrect routing, configuration, deployment, or use.
