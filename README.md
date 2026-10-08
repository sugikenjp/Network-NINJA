# Network-NINJA

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Turn unused network space into Active Trap Zones: routing-based detection surfaces built through intentional network design.**

Network-NINJA is an open-source, distributed detection system that detects unexpected traffic inside enterprise networks. Lightweight sensors run as containers directly on routers and Layer 3 switches, and a central manager collects their events and manages their configuration.

It combines:

- Existing routers and Layer 3 switches
- Intentional routing design
- Lightweight distributed sensors running on network devices or Linux hosts
- Centralized configuration and monitoring

Network-NINJA itself does not configure or control routing.

Network administrators define **Active Trap Zones**, network ranges where legitimate traffic is not expected, and configure the existing routing infrastructure to direct traffic for those ranges toward Network-NINJA sensors. The sensors observe selected traffic and send detection events to the Network-NINJA Manager.

This approach makes security monitoring part of the network design process.

> Network-NINJA does not replace network design.
> It encourages organizations to understand their networks deeply enough to design security into them.

[日本語版 README](README_ja.md)

---

## Demo

<!-- TODO: Add a screenshot of the Manager Web UI and a short GIF of the detection flow. -->
<!-- Example: ![Manager Web UI](docs/images/manager-ui.png) -->

*Screenshots and a demo recording will be added here.*

---

## Overview

Many organizations operate large, segmented networks across offices, data centers, branches, stores, and other locations.

Some network ranges are actively used, while others are unused, reserved, or intentionally excluded from normal business communication.

Traffic directed toward those ranges can provide a valuable security signal. Such traffic may be associated with:

- Network reconnaissance
- Internal network scanning
- Misconfiguration
- Unauthorized access attempts
- Malware activity
- Suspicious lateral movement

Network-NINJA allows organizations to place lightweight sensors throughout their network, on the network devices already present at each site, and to centrally manage what those sensors monitor.

```
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

## Core Concept: Active Trap Zones

The core idea behind Network-NINJA is simple:

> **Traffic going to a network where legitimate communication is not expected deserves attention.**

An **Active Trap Zone** is a network range that:

- Is not used for legitimate business communication
- Looks plausible enough that an intruder exploring the network would be likely to probe it
- Is routed by the existing network infrastructure to a nearby Network-NINJA sensor

Unlike a traditional honeypot, the trap is not a single decoy host. The trap is built from **address selection, topology, routing, and sensor placement**. Detection is therefore distributed across the network architecture rather than concentrated in one system.

Designing an effective Active Trap Zone requires defenders to anticipate where an intruder is likely to look next. Defenders decide which destinations appear plausible; an intruder decides where to explore. Network-NINJA makes that interaction observable.

```
1. Select a plausible, unused network range as an Active Trap Zone
                         |
                         v
2. Design the required routing
                         |
                         v
3. Configure a router or Layer 3 switch
                         |
                         v
4. Direct traffic for the zone to a Network-NINJA Agent
                         |
                         v
5. Monitor selected protocols and ports
                         |
                         v
6. Generate and collect detection events
```

---

## Relationship to Existing Approaches

Monitoring unused address space is not new. Internet-scale darknets and network telescopes have long used it to observe scanning activity.

Network-NINJA brings this idea inside the enterprise and turns it into a design discipline:

- Active Trap Zones are chosen to look plausible to an intruder exploring internal networks.
- Sensors run as containers on the routers and switches already deployed at each site.
- All sensors are managed centrally through a single Manager.

Network-NINJA does not seek to replace IDS, NDR, honeypot, or deception platforms. It complements them with an early, low-cost signal derived from network design.

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

- Which network ranges become Active Trap Zones
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

For this reason, Network-NINJA is not only a network sensor. It is an approach for incorporating security monitoring into network architecture from the design stage.

```
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

## Validated Platforms

Network-NINJA Agents have been deployed and tested as containers on the following network platforms:

| Vendor            | Platform                  | Device type      | Container environment |
| ----------------- | ------------------------- | ---------------- | --------------------- |
| Cisco             | Catalyst 9300             | Layer 3 switch   | App Hosting           |
| Fujitsu           | Si-R G210                 | Router           | On-box container      |
| Furukawa Electric | FITELnet F220             | Router           | On-box container      |
| MikroTik          | RouterOS v7.23            | Router           | RouterOS container    |

Agents also run on standard Linux hosts and virtual machines with Docker.

Because Network-NINJA relies on standard routing rather than vendor-specific features, the same detection design can be applied across heterogeneous, multi-vendor networks.

<!-- TODO: Add per-platform deployment guides under docs/platforms/ and link them from this table. -->

---

## Architecture

Network-NINJA consists primarily of a **Manager** and one or more **Agents**.

```
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
  Active Trap Zone                  Active Trap Zone
      Traffic                           Traffic
```

The Manager provides centralized management, while Agents operate as distributed network sensors.

The routing required to deliver Active Trap Zone traffic to each Agent is configured separately on the organization's routers or Layer 3 switches.

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

| Service         | Default port |
| --------------- | ------------ |
| Web UI          | TCP/8080     |
| REST API        | TCP/8080     |
| Syslog receiver | UDP/514      |

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

The Agent runs as a container and can be deployed on supported network devices (see [Validated Platforms](#validated-platforms)), servers, virtual machines, or other appropriate Linux environments.

### Router or Layer 3 Switch

The router or Layer 3 switch is not part of the Network-NINJA software.

It remains responsible for routing traffic through the enterprise network. Network administrators configure it to direct traffic for each Active Trap Zone toward a Network-NINJA Agent.

```
Corporate network:     10.0.0.0/8
In-use ranges:         10.1.0.0/16 - 10.20.0.0/16
Active Trap Zone:      10.200.0.0/16  (unused, but looks like a server segment)
Sensor destination:    Network-NINJA Agent
```

This is only a conceptual example. Routing configuration must be designed for the actual network environment.

---

## Traffic Monitoring

Network-NINJA Agents monitor selected traffic based on configuration received from the Manager.

Currently supported traffic types:

- ICMP Echo Request
- ICMP Echo Reply
- TCP port 80, commonly used for HTTP
- TCP port 443, commonly used for HTTPS
- TCP port 445, commonly used for SMB

When multiple traffic types are enabled, the Agent combines them into a packet-capture filter. A conceptual example is:

```
ICMP Echo Request or Reply
or TCP port 80
or TCP port 443
or TCP port 445
```

These protocols and ports can provide visibility into traffic relevant to:

- Network reconnaissance
- Unauthorized service discovery
- Unexpected access attempts
- Malware activity
- Lateral movement
- Communication caused by configuration errors

Network-NINJA does not classify traffic as malicious based solely on a protocol or port number. TCP ports 80 and 443, for example, are widely used for legitimate communication.

The security value comes from the combination of:

- Where the traffic was observed
- Whether legitimate communication was expected
- Which source generated the traffic
- Which Active Trap Zone was accessed
- Which protocol or port was used
- The surrounding operational context

Traffic reaching a deliberately designed Active Trap Zone therefore provides a much stronger signal than the port number alone.

---

## Example Detection Scenario

Assume an organization primarily uses the following private address space:

```
10.0.0.0/8
```

The organization selects an unused range that an intruder would plausibly expect to contain servers, designates it as an Active Trap Zone, and configures a route toward a nearby Network-NINJA Agent.

```
Workstation or compromised host
              |
              | Reconnaissance traffic
              v
       Router / L3 Switch
              |
              | Administrator-defined route
              | for the Active Trap Zone
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

If a host performs reconnaissance and sends ICMP, HTTP, HTTPS, or SMB traffic toward the Active Trap Zone, the Agent observes the matching traffic and generates an event identifying the source, the sensor, and the targeted range.

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

Network-NINJA is designed for environments containing multiple network locations, such as:

- Headquarters
- Data centers
- Branch offices
- Stores
- Remote sites
- Network aggregation points

Because Agents can run directly on routers and Layer 3 switches, each location can host a sensor without a dedicated monitoring appliance.

```
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
- Containerized Agents validated on multi-vendor network devices
- Configurable packet monitoring
- ICMP Echo Request and Reply monitoring
- TCP/80, TCP/443, and TCP/445 monitoring
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

- Detect earlier: prevention alone is not enough
- Route what matters instead of mirroring everything
- The network architecture itself becomes part of the trap
- Turn network knowledge into a defensive capability
- Design networks not only to move traffic, but to detect attackers
- Separation of routing and sensing responsibilities
- Detection rather than blocking

---

## Repository Structure

```
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

### Manager

- Linux environment
- Docker and Docker Compose, or Python with Flask
- Network access from Agents
- Permission to receive Syslog traffic
- Persistent storage for the SQLite database

### Agent

- A validated network device with container support, or a Linux environment with Docker
- Packet-capture permissions
- Network connectivity to the Manager
- Network connectivity to the configured Syslog destination

The container requires additional networking capabilities:

```
NET_RAW
NET_ADMIN
```

---

## Starting the Manager

### Docker deployment

Docker Compose is the recommended deployment method.

```
cd manager
docker compose up -d
```

Open the Web UI in a browser:

```
http://<manager-address>:8080
```

### Bare-metal or virtual-machine deployment

Install Flask:

```
pip install flask
```

Start the Manager:

```
DB_PATH=./ninja.db \
WEB_PORT=8080 \
SYSLOG_PORT=5514 \
python3 app.py
```

Binding to UDP port 514 may require elevated privileges. When running without those privileges, use a non-privileged port such as `SYSLOG_PORT=5514`.

---

## Starting an Agent

The steps below describe deployment on a Linux host with Docker. For network devices, refer to the device's container documentation and the [Validated Platforms](#validated-platforms) section.

### 1. Build the container image

```
cd agent
docker build -t ninja-agent .
```

### 2. Start the Agent

```
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

For environments using a dedicated macvlan network, replace `--network=host` with `--network=<macvlan-network-name>`.

The correct network configuration depends on the host platform and network design.

---

## Environment Variables

| Variable        | Required | Description                                  | Example                     |
| --------------- | -------- | -------------------------------------------- | --------------------------- |
| `MANAGER_URL`   | Yes      | URL of the Network-NINJA Manager             | `http://192.168.1.100:8080` |
| `SYSLOG_SERVER` | Yes      | IP address of the Syslog destination         | `192.168.1.100`             |
| `SYSLOG_PORT`   | No       | Syslog destination port, default `514`       | `514`                       |
| `NODE_ID`       | No       | Unique node identifier, defaults to hostname | `agent-sw01`                |
| `NODE_LABEL`    | No       | Display name shown in the Manager            | `Switch-01 (1F)`            |

Additional traffic-monitoring options are distributed through the Manager configuration.

---

## Agent Operation

Each Agent performs two periodic management functions.

### Heartbeat

The Agent sends a heartbeat to the Manager every 30 seconds. The Manager uses the last heartbeat time to determine node status.

| Status    | Condition                                      |
| --------- | ---------------------------------------------- |
| `ONLINE`  | Last heartbeat received within two minutes     |
| `OFFLINE` | More than two minutes since the last heartbeat |

### Configuration polling

The Agent polls the Manager for configuration updates every 60 seconds.

```
GET /api/config/<node_id>
```

When a changed configuration is detected, the Agent restarts its monitoring process with the updated settings.

---

## REST API

| Method   | Path                   | Description                             |
| -------- | ---------------------- | --------------------------------------- |
| `POST`   | `/api/heartbeat`       | Receive an Agent heartbeat              |
| `GET`    | `/api/nodes`           | Retrieve the node list                  |
| `DELETE` | `/api/nodes/:id`       | Delete a node                           |
| `GET`    | `/api/syslogs`         | Retrieve and search Syslog records      |
| `GET`    | `/api/syslogs/count`   | Retrieve the total Syslog record count  |
| `POST`   | `/api/config/deploy`   | Deploy configuration to multiple Agents |
| `GET`    | `/api/config/:node_id` | Retrieve configuration for an Agent     |

Example query parameters for retrieving Syslog records:

```
q=<search-text>
source=<source-address>
limit=<maximum-results>
```

---

## Configuration Deployment

The Manager can distribute configuration to multiple Agents.

```
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

```
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

The Manager stores data in SQLite. The default database path is `/data/ninja.db`.

| Table              | Purpose                                                  |
| ------------------ | -------------------------------------------------------- |
| `nodes`            | Node information, last heartbeat time, and configuration |
| `syslogs`          | Received Syslog records                                  |
| `config_templates` | Configuration deployment history                         |

---

## Viewing Agent Logs

```
docker logs -f ninja-agent
```

Stop the Agent:

```
docker stop ninja-agent
```

Remove the Agent container:

```
docker rm ninja-agent
```

---

## Network Design Considerations

Before deploying Network-NINJA, review the following:

- Confirm that each Active Trap Zone is not used by legitimate systems.
- Choose ranges that are plausible targets for internal reconnaissance in your environment.
- Confirm that routing changes will not interrupt production traffic.
- Identify monitoring, management, and troubleshooting traffic that may require exclusions.
- Determine which sensor should receive traffic for each Active Trap Zone.
- Validate return-path behavior where applicable.
- Confirm that the Agent can observe traffic delivered by the network infrastructure.
- Test routing and detection in a controlled environment.
- Document the purpose and ownership of each Active Trap Zone.
- Ensure that routing configurations are managed through the organization's normal change-control process.

Network-NINJA does not automatically validate the organization's routing design. The network administrator remains responsible for ensuring that the design is safe and appropriate for the environment.

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

A detection event indicates that selected traffic reached a Network-NINJA sensor. Possible causes include:

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

### Early detection of internal reconnaissance

Detect hosts probing Active Trap Zones with ICMP, HTTP/HTTPS, or SMB before reconnaissance develops into broader lateral movement.

### Detection of unexpected network access

Observe traffic directed toward networks where normal communication is not expected.

### Distributed branch monitoring

Deploy lightweight Agents on the routers and switches already present at branches, stores, or remote locations.

### SMB activity monitoring

Observe TCP/445 traffic reaching Active Trap Zones.

### Security architecture validation

Verify whether network segmentation and expected communication paths behave as designed.

### Security by Design exercises

Use the design of Active Trap Zones and sensor locations to deepen understanding of the organization's topology and routing architecture.

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

If you find a bug or would like to suggest an improvement, open an Issue in this repository. When reporting a problem, include:

- Manager or Agent component
- Deployment method and platform
- Relevant configuration
- Expected behavior
- Actual behavior
- Relevant logs with sensitive information removed

---

## License

Network-NINJA is released under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Author

**Ken Sugio**

Cybersecurity and network security researcher and engineer.

Areas of interest include network security, network monitoring, network architecture, network deception, Security by Design, Zero Trust, threat detection, and distributed security sensors.

---

## Disclaimer

Network-NINJA is intended for authorized defensive security, research, education, and testing purposes.

Users are responsible for ensuring that deployment, routing configuration, monitoring, data collection, and testing comply with applicable laws, regulations, contracts, and organizational policies.

The authors and contributors are not responsible for damage or disruption caused by incorrect routing, configuration, deployment, or use.
