# Check Point Central Deployment Tool (CDT) — Discussion Summary

**Purpose:** Briefing document for discussing CDT and automation of Check Point upgrade/deployment processes.
**Prepared:** 2026-07-08
**Current CDT version:** v2.2 (released 31 Jul 2025)

---

## 1. Executive Summary

The **Central Deployment Tool (CDT)** is a free Check Point utility that runs on **Security Management Servers** and **Multi-Domain Security Management Servers** (Gaia OS). It lets an administrator push and install software packages (upgrades, Hotfixes, Jumbo Hotfix Accumulators) to **many managed Security Gateways and Cluster Members at the same time**, from a single central point — instead of doing each gateway manually.

CDT is the primary Check Point-supported way to **automate large-scale gateway upgrade and maintenance operations**, and it handles the hard parts of clustering (failover, Connectivity Upgrade) automatically.

**Why it matters for automation:**
- One operation → many gateways/clusters in parallel.
- Automatic, safe cluster upgrades (failover orchestration handled for you).
- Scriptable via Expert-mode CLI, Gaia Clish (with Role-Based Access Control), pre/post user scripts, and deployment plans.
- Complements the **Ansible `check_point.mgmt` collection** for end-to-end infrastructure-as-code workflows.

---

## 2. What CDT Does

| Capability | Description |
|---|---|
| **Install software packages** | Upgrades, Hotfixes, Jumbo Hotfix Accumulators pushed centrally via CPUSE offline packages. |
| **Custom actions** | Take snapshots, run shell scripts, push/pull files, run commands. |
| **RMA automation** | Automates the RMA backup and restore process for appliance replacement. |
| **Cluster handling** | Automatically orchestrates cluster upgrades including Connectivity Upgrade (CU) and failover. |

**Supported target types:** Security Gateways, ClusterXL (High Availability), VRRP clusters, VSX gateways/clusters (HA and VSLS), Maestro (single/multi-site), and CloudGuard Network (Azure/AWS/GCP/NSX).

---

## 3. High-Level Workflow (what CDT does under the hood)

**Single Security Gateway upgrade:**
1. Validate gateway state (all processes up).
2. Prepare Access Control Policy (update version in object, adjust config/policy).
3. Execute the Deployment Plan:
   - Run **Pre-Script(s)**
   - Update CPUSE version
   - Push CPUSE package(s) to the gateway
   - Import package(s)
   - Install package(s)
   - Validate policy is installed
   - Run **Post-Script(s)**
4. Re-validate gateway state.

**Cluster (High Availability) upgrade** adds automatic **failover orchestration**: upgrade Standby members first → validate → fail over → upgrade former Active member → re-validate Active/Standby states. Full Connectivity Upgrade is supported.

**Maestro upgrade** groups members by site/role (Backup → Standby → Active), upgrades non-Active groups in parallel, then performs failover before upgrading the former Active group.

**Hotfix install** follows the same push/import/install/validate flow but without the cluster version change.

> Basic flow: **Generate Candidates List → (edit/select targets) → Run CDT (prepare/install) → Validate.**

---

## 4. Operation Modes (key for planning maintenance windows)

| Mode | What it does | Automation / MW benefit |
|---|---|---|
| **Basic mode** | Single package defined in `CentralDeploymentTool.xml` (`PackageToInstall`). Simple installs. | Quickest to configure. |
| **Advanced mode** | Uses a **Deployment Plan (XML)** with multiple ordered actions (scripts, file push/pull, snapshots, installs). | Full flexibility; the core of complex automation. |
| **Preparations mode** | Delivers CPUSE Agent + offline package to gateways **without installing** — no connectivity loss. | Pre-stage packages *before* the maintenance window → install phase becomes very fast. |
| **Extended preparations** | Preparations + update CPUSE Agent + import & verify package (still no install). May cause brief connectivity loss (CPUSE update). | Even less work left during the window. |
| **Retry mode** | Re-run only failed installations. Can run multiple instances. | Recover quickly from partial failures. |
| **RMA mode** | Automated backup/restore for appliance replacement. | Standardized RMA process. |

**Talking point:** Preparations mode is the single biggest lever for shrinking a 's maintenance window — heavy file transfer happens ahead of time; only the install/reboot happens during the window.

---

## 5. How CDT Is Driven (interfaces & automation surfaces)

### a) Expert-mode CLI (primary)
- Binary: `$CDTDIR/CentralDeploymentTool` (`$CDTDIR` = `/opt/CPcdt/`).
- Generate candidates + run installs:
  ```
  $CDTDIR/CentralDeploymentTool -generate -candidates=<file.csv> -deploymentplan=<plan.xml> -filter=<filter_file>
  ```
- Check version: `$CDTDIR/CentralDeploymentTool -v`
- **Run detached so SSH drops don't kill it** (important for automation):
  ```
  nohup /path_to_CDT/CentralDeploymentTool [options]
  ```
- The process is **blocking**, so a wrapper Bash script can run: pre-actions → CDT → post-actions in sequence.

### b) Gaia Clish integration (since CDT v1.9.0; integrated in R81.10+)
Enables CDT via **Gaia Dynamic CLI** with **Role-Based Access Control** — so you can grant upgrade rights *without* handing out Expert-mode passwords.
- Commands: `show cdt ...`, `set cdt ...`, `start cdt ...`
- Examples:
  ```
  start cdt generate-candidates deployment-plan "<plan>" candidates-list "<list>.csv" server <MgmtIP>
  set cdt candidates candidates-list "<list>.csv" enable-candidate <GW_Object> server <MgmtIP>
  start cdt execute deployment-plan "<plan>" candidates-list "<list>.csv" server <MgmtIP>
  show cdt status server <MgmtIP>
  ```
- Permissions: `show cdt` needs none; `set cdt` and `start cdt` require the **`cdt` feature with Read/Write** in the user role.
- File repositories (Clish users): candidates in `/opt/CPcdt/CandidateListsRepository/`, plans in `/opt/CPcdt/DeploymentPlanRepository/`.
- `session <name>` parameter (CDT v1.9.8+) allows **multiple concurrent CDT sessions**.

### c) Configuration & data files
- `CentralDeploymentTool.xml` — primary config (logging level, debug flags, package to install in Basic mode).
- **Candidates List (CSV)** — the list of target gateways/clusters; edit the "Upgrade order" column to select/deselect (only numbers, `-`, or `N/A` allowed).
- **Deployment Plan (XML)** — ordered set of actions for Advanced mode.
- **User scripts** — pre/post scripts run on gateways (must not reboot directly; exit code `222` tells CDT to reboot).

### d) Ansible integration (infrastructure-as-code angle) — see Section 8.

---

## 6. Requirements & Prerequisites

- Runs on Gaia **Security Management** or **Multi-Domain Security Management** servers.
- Must be executed by a user with **admin Gaia role (UID 0)** in **Expert mode** (or via Clish RBAC with the `cdt` feature).
- Install: unpack TGZ/TAR, then `rpm -Uhv --force CPcdt-00-00.i386.rpm`. Files land in `/opt/CPcdt/`.
- **Upgrade order rule:** the Management Server (and Log Servers) must be at the target version **or higher** *before* upgrading gateways/clusters (exception: with the right Jumbo Hotfix + `SkipVerifySupportedByOS` flag).
- CPUSE offline packages are delivered by CDT (it forces CPUSE to work offline).

### CDT version ↔ Management Server support

| CDT Version | Supported Management Server Versions |
|---|---|
| 2.2 / 2.1 | R81.10 → R82.10 |
| 2.0 | R80.10 → R82 |
| 1.9.5 – 1.9.8 | R80.10 → R81.20 |

---

## 7. Key Limitations

**Not supported on:** Standalone servers, Management in Backup state (HA), dedicated SmartEvent/Log servers, Multi-Domain Log Server, Full HA cluster members, Scalable Chassis 40000/60000, Spark firewalls, SmartProvisioning-managed ROBO gateways, IPv6-only gateways, globally-used gateways on MDS, Maestro multi-site Active-Active, VSNext.

**Cluster modes:** Does **not** support ClusterXL Load Sharing (Multicast or Unicast).

**Upgrade constraints:**
- No upgrade from R80.10 / R80.20 / R80.30 (use CPUSE in-place upgrade instead).
- No **clean install of a major version** (except RMA mode).
- No packages containing RPM files (e.g., CPInfo package).
- No major upgrade of gateways running QoS Policy or Desktop Policy.
- **Only Access Control policy is installed** by CDT — **Threat Prevention, QoS, and Desktop policies must be installed manually** from SmartConsole afterward (Threat Prevention is auto-installed on CDT v1.9.7+).

**Operational:**
- **Cannot** be run as a scheduled Gaia job (no cron).
- Only **one CDT process at a time** on a single Management Server (parallel is allowed per-Domain on MDS, or in Retry mode).
- Back up the Management Server before upgrading VSX gateways/clusters.

**CloudGuard:** Supported R80.10+ on Azure/AWS/GCP/NSX; disable auto-scaling during Hotfix deployment on Scale Sets / Auto Scaling Groups.

### ⚠️ Top Automation Gotchas (read before you script anything)

| # | Gotcha | Why it bites automation | Mitigation |
|---|---|---|---|
| 1 | **An SSH drop kills the run** | If the SSH session that launched CDT disconnects, `CentralDeploymentTool` dies mid-install. | Always launch with `nohup … &`, or start it from a control node (Ansible/AWX) that holds the session. |
| 2 | **No native Gaia scheduler** | You *cannot* run CDT as a Gaia cron/scheduled job. | Trigger from an external scheduler (Ansible/AWX/Jenkins/cron on a control node) over SSH or the API. |
| 3 | **One CDT instance per Mgmt** | A second CDT on the same SMS fails (“cannot run multiple instances”). | Guard with `pidof CentralDeploymentTool`. On MDS, run one per Domain with **separate** candidate files. |
| 4 | **Only Access Control policy is installed** | Threat Prevention / QoS / Desktop policy are **not** auto-installed (TP auto-installs on v1.9.7+). | Add a post-step to install the rest (SmartConsole or `cp_mgmt_install_policy`). |
| 5 | **Mgmt must be upgraded first** | CDT refuses to push a version *higher* than the Management/Log servers. | Upgrade SMS + Log Servers to the target version **before** the gateway run. |
| 6 | **Candidates list goes stale** | Any DB change after generation → “list invalid, regenerate.” | Regenerate the CSV as the **first** step of every automated run. |
| 7 | **Edit only the `Upgrade Order` column** | Touching any other column/value corrupts the list. Only numbers, `-`, `N/A` are valid. | Script edits to the **last column only**; never change `N/A` or `Installed`. |
| 8 | **User scripts must never reboot** | A `reboot` inside a pre/post script breaks CDT's flow; a missing return code fails the action. | Let CDT reboot. If a reboot is required, `exit 222`. Always exit with a return code. |
| 9 | **Blocking by default** | Every action is `iscritical="true"` — one failure stops the whole deployment for that GW/cluster. | Mark non-essential actions `iscritical="false"`; use **Retry**/**Resume** to continue failed targets. |
| 10 | **CPUSE self-update mismatch** | One cluster member pulls a newer CPUSE Agent build and refuses to install while its peer succeeds. | Stage the **latest** CPUSE Agent RPM in the repo so all members match before the run. |
| 11 | **Unsupported topologies** | ClusterXL Load Sharing, Full-HA members, Maestro Active-Active, VSNext, Spark, IPv6-only, 40000/60000 chassis are all unsupported. | Exclude them from candidate lists (`-`); handle out-of-band. |
| 12 | **VSX = back up Mgmt first** | VSX upgrades are higher-risk; RMA backup fails on VSX VSLS members. | Take a snapshot **and** a Mgmt backup before VSX runs; don't rely on RMA for VSLS. |
| 13 | **No RPM-content packages / no clean major install** | CDT can't install packages containing RPMs (e.g., CPInfo) or do a clean major install (except RMA). | Use CPUSE **offline** upgrade/hotfix packages only. |

---

## 8. CDT vs. Ansible `cp_mgmt_install_software_package` (automation comparison)

Check Point offers an **Ansible module** (`check_point.mgmt.cp_mgmt_install_software_package`, part of the `check_point.mgmt` collection) that installs packages via the **Management API (Web Services)** — a different, complementary automation path.

| Aspect | **CDT** | **Ansible `cp_mgmt_install_software_package`** |
|---|---|---|
| Interface | Runs locally on Mgmt server (CLI / Clish) | Runs over **Management API** (remote, from a control node) |
| Availability | Any supported Gaia Mgmt server | Management **R80.40+** (method/location options R81+) |
| Cluster orchestration | **Automatic** failover / Connectivity Upgrade | Cluster settings via `cluster_installation_settings` (strategy, delay); less hands-off |
| Parallelism control | Batches / groups internally | `concurrency_limit`, `targets` list |
| Fit | Deep, Check Point-native upgrade orchestration (RMA, VSX, Maestro, CU) | Fits cleanly into existing **Ansible / IaC / CI-CD pipelines** |
| Package source | CPUSE offline packages delivered by CDT | `package_location`: `automatic` / `target-machine` / `central` |

**Key `cp_mgmt_install_software_package` parameters** (verified against the module source, collection `check_point.mgmt`):

| Parameter | Type | Notes |
|---|---|---|
| `name` | string | Package file name as it appears in the repository. |
| `targets` | list | Gateway/cluster **object names or UIDs**. |
| `method` | string | `install` or `upgrade` (R81+). |
| `package_location` | string | `automatic` / `target-machine` / `central` (R81+). |
| `concurrency_limit` | integer | Parallel targets (API default `10`). |
| `cluster_installation_settings` | dict | `cluster_delay` (int, seconds) + `cluster_strategy` (**free-form string** forwarded to the API — the module does not restrict values). |
| `version` | string | Target version; latest if omitted. |
| `wait_for_task` | bool | Default `true`. |
| `wait_for_task_timeout` | integer | Minutes; default `30`. |
| `auto_publish_session` | bool | Default `false`. |

**Minimal example** (the full, real end-to-end pipeline is in §9.7):
```yaml
- name: Install a Jumbo Hotfix on one gateway
  check_point.mgmt.cp_mgmt_install_software_package:
    name: Check_Point_R82_JUMBO_HF_T30_FULL.tgz
    package_location: automatic
    targets:
      - corporate-gateway
    wait_for_task: true
```

**Recommendation for the customer:**
- Use **CDT** when you need **robust, Check Point-native mass upgrade orchestration** (clusters, VSX, Maestro, Connectivity Upgrade, RMA) with minimal manual failover handling.
- Use the **Ansible module** when the customer already standardizes on **Ansible / infrastructure-as-code** and wants package installs as part of a broader, API-driven, remotely-triggered pipeline.
- These are **not mutually exclusive** — Ansible can orchestrate the surrounding workflow while CDT (invoked via a task/script, or via Clish) does the heavy cluster upgrade lifting.

---

## 9. Detailed Automation Use Cases & Worked Examples

This section contains ready-to-adapt, end-to-end examples. Use these to show the exactly *what automating with CDT looks like in practice*.

### 9.0 The three building blocks of every CDT run

| Artifact | File | Purpose |
|---|---|---|
| **Primary config** | `$CDTDIR/CentralDeploymentTool.xml` | Global settings: path to CPUSE RPM, logging, email, and (Basic mode only) the single `PackageToInstall` + pre/post scripts. |
| **Candidates List** | `*.csv` (any name/path; Clish repo: `/opt/CPcdt/CandidateListsRepository/`) | The list of eligible gateways/clusters. You edit **only the last column, `Upgrade Order`**, to select targets and batch order. |
| **Deployment Plan** | `*.xml` (any name/path; Clish repo: `/opt/CPcdt/DeploymentPlanRepository/`) | Advanced mode only: the ordered list of actions (snapshot, scripts, install, push/pull, email, …). |

**`Upgrade Order` column values (the only column you may edit):**

| Value | Meaning |
|---|---|
| `1`, `2`, `3`, … | **Batch number.** All targets with the same number install **in parallel**; batches run in ascending order (batch 1 finishes before batch 2 starts). |
| `-` (hyphen) | **Exclude** this target from this run. |
| `N/A` | Not eligible for this package. **Set by CDT — do not change.** |
| `Installed` | Package already present. **Set by CDT — do not change.** |

> **Cluster rule:** all members of the same cluster **must share the same batch number**. CDT still upgrades them safely one role at a time internally (Standby → failover → former Active).

CLI syntax differs slightly between modes:
- **Basic mode** uses a *positional* candidates path: `-generate <file>.csv`, `-install <file>.csv`.
- **Advanced mode** uses *named* flags: `-generate -candidates=<file>.csv -deploymentplan=<plan>.xml` and `-execute ...`.
- On a **Multi-Domain Server**, first run `mdsenv <DomainIP>` and append `-server=<DomainIP>` (Advanced) or the Domain IP (Basic).

---

### 9.1 Use Case A — Automated upgrade of a SINGLE Security Gateway (Advanced mode)

**Scenario:** Upgrade standalone gateway `GW-Perimeter` from R81.10 → R82, with a safety snapshot, a pre-flight health check, the upgrade, a post-check, evidence pulled back, and an email — fully unattended.

**Step 1 — Deployment Plan** (`/opt/CPcdt/DeploymentPlanRepository/upgrade_single_gw.xml`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<CDT_Deployment_Plan>
  <plan_settings>
    <name value="Upgrade_GW-Perimeter_R81.10_to_R82" />
    <description value="Single gateway upgrade with snapshot and pre/post checks" />
    <update_cpuse value="true" />           <!-- refresh CPUSE Agent first -->
    <connectivityupgrade value="true" />
  </plan_settings>

  <!-- 1. Announce start -->
  <log level="ALWAYS" value="Starting upgrade of GW-Perimeter to R82" />

  <!-- 2. Safety snapshot BEFORE touching the gateway -->
  <create_snapshot name="pre_R82_upgrade" description="Auto snapshot by CDT before R82" />

  <!-- 3. Pre-flight health check (script lives on the Mgmt server, runs ON the GW) -->
  <execute_script path="/opt/CPcdt/scripts/pre_check.sh" />

  <!-- 4. Send + import + install the upgrade package (all in one action) -->
  <install_package path="/opt/CPcdt/packages/Check_Point_R82_T631_Fresh_Install_and_Upgrade.tgz" />

  <!-- 5. Post-install verification (non-blocking: reporting issues won't fail the run) -->
  <execute_script path="/opt/CPcdt/scripts/post_check.sh" iscritical="false" />

  <!-- 6. Pull the post-check log back to the Mgmt server for the record -->
  <pull_file remote_path="/var/log/cdt_post_check.log" local_dir="/opt/CPcdt/results/" iscritical="false" />

  <!-- 7. Notify the team -->
  <send_email to="netops@example.com" subject="CDT: GW-Perimeter upgraded to R82"
              body="Upgrade completed. See post-check log on the Mgmt server." />
  <log level="ALWAYS" value="Finished upgrade of GW-Perimeter" />
</CDT_Deployment_Plan>
```

**Step 2 — Pre-check user script** (`/opt/CPcdt/scripts/pre_check.sh`, runs **on the gateway**):
```bash
#!/bin/bash
# Runs ON the Security Gateway before upgrade. Must exit with a return code.
# NEVER reboot here. (Use exit 222 only if you WANT CDT to reboot the GW.)

# Firewall daemon must be up
if ! cpwd_admin list | grep -q "FWD"; then
    echo "FWD not running - aborting" > /var/log/cdt_pre_check.log
    exit 1
fi

# Require at least 5 GB free on /var/log
FREE=$(df -Pk /var/log | awk 'NR==2 {print $4}')
if [ "$FREE" -lt 5242880 ]; then
    echo "Not enough free space on /var/log" >> /var/log/cdt_pre_check.log
    exit 1
fi

echo "Pre-checks passed on $(hostname) at $(date)" > /var/log/cdt_pre_check.log
exit 0
```

**Step 3 — Candidates List** (representative — CDT generates all columns; you edit only `Upgrade Order`):
```csv
Name,Type,IP Address,Installed Version,Upgrade Order
GW-Perimeter,Gateway,10.10.10.5,R81.10,1
GW-Branch2,Gateway,10.20.0.5,R81.10,-
CL-DC1_A,Cluster Member,10.10.1.11,R81.10,N/A
```
*`GW-Perimeter` → batch 1 (will upgrade); `GW-Branch2` → `-` (excluded); the cluster member → `N/A` (not eligible for this plan, left untouched).*

**Step 4 — Run it:**
```bash
# 1) Generate the candidates list from the plan
$CDTDIR/CentralDeploymentTool -generate \
  -candidates=/opt/CPcdt/CandidateListsRepository/gw_perimeter.csv \
  -deploymentplan=/opt/CPcdt/DeploymentPlanRepository/upgrade_single_gw.xml

# 2) Edit gw_perimeter.csv: set Upgrade Order = 1 for GW-Perimeter, "-" for others

# 3) Execute — detached so an SSH drop won't abort it
nohup $CDTDIR/CentralDeploymentTool -execute \
  -candidates=/opt/CPcdt/CandidateListsRepository/gw_perimeter.csv \
  -deploymentplan=/opt/CPcdt/DeploymentPlanRepository/upgrade_single_gw.xml &

# 4) Monitor live
watch -d cat $CDTDIR/CDT_status.txt
```

---

### 9.2 Use Case B — Automated upgrade of an HA CLUSTER with Connectivity Upgrade (zero-downtime)

**Scenario:** Upgrade ClusterXL cluster `CL-DC1` (members `CL-DC1_A`, `CL-DC1_B`) from R81.10 → R82 while **keeping connections alive** across the failover. You write the **same kind of plan** as a single gateway — CDT handles the member ordering and failover for you.

**Step 1 — Deployment Plan** (`/opt/CPcdt/DeploymentPlanRepository/upgrade_cluster.xml`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<CDT_Deployment_Plan>
  <plan_settings>
    <name value="Upgrade_CL-DC1_R81.10_to_R82" />
    <description value="HA ClusterXL upgrade with Connectivity Upgrade" />
    <update_cpuse value="true" />
    <connectivityupgrade value="true" />   <!-- keeps connections alive across failover -->
  </plan_settings>

  <log level="ALWAYS" value="Starting Connectivity Upgrade of cluster CL-DC1 to R82" />
  <create_snapshot name="pre_R82_CL-DC1" description="Snapshot before cluster upgrade" />
  <execute_script path="/opt/CPcdt/scripts/pre_check.sh" />
  <install_package path="/opt/CPcdt/packages/Check_Point_R82_T631_Fresh_Install_and_Upgrade.tgz" />
  <execute_script path="/opt/CPcdt/scripts/post_check.sh" iscritical="false" />
  <send_email to="netops@example.com" subject="CDT: Cluster CL-DC1 upgraded to R82"
              body="Cluster Connectivity Upgrade completed." />
  <log level="ALWAYS" value="Finished Connectivity Upgrade of cluster CL-DC1" />
</CDT_Deployment_Plan>
```

**Step 2 — Candidates List** — both members **must have the same batch number**:
```csv
Name,Type,Cluster,IP Address,Installed Version,Upgrade Order
CL-DC1_A,Cluster Member,CL-DC1,10.10.1.11,R81.10,1
CL-DC1_B,Cluster Member,CL-DC1,10.10.1.12,R81.10,1
```

**Step 3 — Run it** (same commands, cluster files):
```bash
$CDTDIR/CentralDeploymentTool -generate \
  -candidates=/opt/CPcdt/CandidateListsRepository/cluster.csv \
  -deploymentplan=/opt/CPcdt/DeploymentPlanRepository/upgrade_cluster.xml

nohup $CDTDIR/CentralDeploymentTool -execute \
  -candidates=/opt/CPcdt/CandidateListsRepository/cluster.csv \
  -deploymentplan=/opt/CPcdt/DeploymentPlanRepository/upgrade_cluster.xml &

watch -d cat $CDTDIR/CDT_status.txt
```

**What CDT does automatically (you do NOT script any of this):**
1. Validates cluster health (one Active, one Standby).
2. Updates the cluster object version and prepares the Access Control policy.
3. Upgrades the **Standby** member first (pre-script → CPUSE → push → import → install → policy validation → post-script).
4. Performs a **controlled failover** to the upgraded member (Connectivity Upgrade keeps sessions alive).
5. Upgrades the **former Active** member.
6. Re-validates that the cluster is back to Active/Standby.

> **Key selling point:** the admin's plan is identical to a single gateway — the entire failover choreography is CDT's job, not the operator's.

---

### 9.3 Use Case C — Mass Jumbo Hotfix across many gateways in PHASED batches (Basic mode)

**Scenario:** Push one Jumbo Hotfix Accumulator to a lab gateway first (canary), then branches, then the datacenter cluster — automatically, in waves.

**Step 1 — `CentralDeploymentTool.xml`** (Basic mode: one package + optional scripts):
```xml
<PackageToInstall value="/opt/CPcdt/packages/Check_Point_R82_JUMBO_HF_T30_FULL.tgz" />
<CPUSE value="/sysimg/CPwrapper/linux/CPda/CPda-00-00.i386.rpm" />
<PreInstallationScript  value="/opt/CPcdt/scripts/pre_check.sh"  IsBlocking="true"  />
<PostInstallationScript value="/opt/CPcdt/scripts/post_check.sh" IsBlocking="false" />
```

**Step 2 — Candidates List with wave/batch numbers:**
```csv
Name,Type,IP Address,Installed Version,Upgrade Order
GW-Lab1,Gateway,10.99.0.10,R82,1
GW-Branch1,Gateway,10.21.0.5,R82,2
GW-Branch2,Gateway,10.22.0.5,R82,2
GW-Branch3,Gateway,10.23.0.5,R82,3
CL-DC1_A,Cluster Member,10.10.1.11,R82,4
CL-DC1_B,Cluster Member,10.10.1.12,R82,4
```
*Batch 1 = canary (`GW-Lab1`). When it succeeds, batch 2 runs the two branches **in parallel**, then batch 3, then batch 4 (the cluster — both members same batch).*

**Step 3 — Run it (Basic mode, positional path):**
```bash
$CDTDIR/CentralDeploymentTool -generate /opt/CPcdt/jhf_candidates.csv
# edit the Upgrade Order column into waves as above
nohup $CDTDIR/CentralDeploymentTool -install /opt/CPcdt/jhf_candidates.csv &
watch -d cat $CDTDIR/CDT_status.txt
```

---

### 9.4 Use Case D — Shrinking the maintenance window (two-phase: Preparations → Install)

**Scenario:** Bandwidth to remote gateways is limited; the maintenance window is short. Pre-stage everything the day before with **no connectivity impact**, then do a fast install during the window.
```bash
# --- Day before the window (NO downtime): push packages + CPUSE Agent to all gateways ---
nohup $CDTDIR/CentralDeploymentTool -preparations /opt/CPcdt/jhf_candidates.csv &

# (Optional) also update CPUSE + import & verify ahead of time — may cause brief blips:
# nohup $CDTDIR/CentralDeploymentTool -extended_preparations /opt/CPcdt/jhf_candidates.csv &

# --- During the window: fast install (files already on the gateways) ---
nohup $CDTDIR/CentralDeploymentTool -install /opt/CPcdt/jhf_candidates.csv &
watch -d cat $CDTDIR/CDT_status.txt
```
> Because the heavy file transfer already happened, only import/install/reboot occurs in the window.

---

### 9.5 Use Case E — Fully unattended wrapper script (pre-checks + notifications)

**Scenario:** A single self-contained driver on the Management Server that guards against a second CDT instance, regenerates a fresh candidates list, runs the plan, and emails the result. Launch it with `nohup ./run_cdt_upgrade.sh &`.
```bash
#!/bin/bash
# run_cdt_upgrade.sh — unattended CDT driver on the Management Server
set -euo pipefail
CDTDIR=/opt/CPcdt
PLAN=$CDTDIR/DeploymentPlanRepository/upgrade_cluster.xml
CANDIDATES=$CDTDIR/CandidateListsRepository/cluster.csv
STATUS=$CDTDIR/CDT_status.txt

# 1) Refuse to start if another CDT instance is already running
if pidof CentralDeploymentTool >/dev/null; then
  echo "Another CDT instance is running. Aborting." | mail -s "CDT aborted" netops@example.com
  exit 1
fi

# 2) Regenerate a fresh candidates list (the DB may have changed since last time)
$CDTDIR/CentralDeploymentTool -generate -candidates="$CANDIDATES" -deploymentplan="$PLAN"

# 3) Execute the deployment plan (CDT is blocking — the script waits here)
$CDTDIR/CentralDeploymentTool -execute -candidates="$CANDIDATES" -deploymentplan="$PLAN"

# 4) Report the outcome
if grep -qi "failed" "$STATUS"; then
  mail -s "CDT upgrade FAILED" netops@example.com < "$STATUS"
  exit 1
else
  mail -s "CDT upgrade SUCCESS" netops@example.com < "$STATUS"
fi
```

---

### 9.6 Use Case F — Operator-driven run via Gaia Clish + RBAC (no Expert password)

**Scenario:** A NOC operator with a Gaia role that has the `cdt` feature (Read/Write) runs the upgrade **without** Expert-mode credentials. File names are relative to the CDT Clish repositories.
```clish
# 1) Generate the candidates list
start cdt generate-candidates deployment-plan "upgrade_cluster.xml" \
     candidates-list "cluster.csv" server 10.0.0.10

# 2) Select targets (enable/disable specific objects)
set cdt candidates candidates-list "cluster.csv" enable-candidate CL-DC1_A server 10.0.0.10
set cdt candidates candidates-list "cluster.csv" enable-candidate CL-DC1_B server 10.0.0.10

# 3) Execute the plan
start cdt execute deployment-plan "upgrade_cluster.xml" \
      candidates-list "cluster.csv" server 10.0.0.10

# 4) Monitor
show cdt status server 10.0.0.10
```

---

### 9.7 Use Case G — Ansible orchestration (real, end-to-end)

There are two integration patterns. **Pattern 1** drives the **Management API** with real `check_point.mgmt` modules. **Pattern 2** lets Ansible *trigger CDT itself* over SSH so you keep CDT's native cluster/VSX/Maestro/Connectivity-Upgrade orchestration.

#### Prerequisites (both patterns for the API part)
```bash
# On the Ansible control node
ansible-galaxy collection install check_point.mgmt
```

**Inventory** (`inventory.ini`) — the API uses an **httpapi** connection to the Management Server:
```ini
[cp_mgmt]
mgmt ansible_host=10.0.0.10

[cp_mgmt:vars]
ansible_connection=httpapi
ansible_network_os=check_point.mgmt.checkpoint
ansible_httpapi_use_ssl=True
ansible_httpapi_validate_certs=False
ansible_httpapi_port=443
ansible_user=automation_admin
ansible_password="{{ vault_cp_password }}"      # keep secrets in ansible-vault, never plaintext
# --- OR authenticate with an API key instead of user/password ---
# ansible_api_key="{{ vault_cp_api_key }}"

# For a Multi-Domain Server, target a specific Domain:
# ansible_checkpoint_domain=Domain-A
```

#### Pattern 1 — Native Management-API pipeline (verify → upgrade cluster → hotfix a GW → post-check → install policy → publish)

Every task below is a **real** module in `check_point.mgmt`:
```yaml
---
- name: Check Point package deployment via the Management API
  hosts: cp_mgmt
  connection: httpapi
  gather_facts: false
  vars:
    upgrade_pkg: Check_Point_R82_T631_Fresh_Install_and_Upgrade.tgz
    jhf_pkg: Check_Point_R82_JUMBO_HF_T30_FULL.tgz
  tasks:
    # 1) Verify the package can be installed on the cluster members (no install, safe)
    - name: Verify upgrade package on the cluster
      check_point.mgmt.cp_mgmt_verify_software_package:
        name: "{{ upgrade_pkg }}"
        targets:
          - CL-DC1_A
          - CL-DC1_B
        download_package: true
        download_package_from: central
        concurrency_limit: 2
        wait_for_task: true

    # 2) Upgrade the HA cluster — stagger members with a delay between them
    - name: Upgrade HA cluster CL-DC1 to R82
      check_point.mgmt.cp_mgmt_install_software_package:
        name: "{{ upgrade_pkg }}"
        targets:
          - CL-DC1_A
          - CL-DC1_B
        method: upgrade
        package_location: central
        cluster_installation_settings:
          cluster_delay: 60          # seconds between members
          # cluster_strategy is a free-form string forwarded to the API.
          # Set it only if your Mgmt version documents accepted values
          # (check the API reference / `mgmt_cli install-software-package`).
          # cluster_strategy: "..."
        wait_for_task: true
        wait_for_task_timeout: 180   # minutes
      register: cluster_upgrade

    # 3) Install a Jumbo Hotfix on a single gateway (one at a time)
    - name: Install JHF on GW-Perimeter
      check_point.mgmt.cp_mgmt_install_software_package:
        name: "{{ jhf_pkg }}"
        targets:
          - GW-Perimeter
        method: install
        package_location: automatic
        concurrency_limit: 1
        wait_for_task: true

    # 4) Post-install health check via run-script (runs ON the gateways)
    - name: Post-upgrade verification script
      check_point.mgmt.cp_mgmt_run_script:
        script_name: "post-upgrade checks"
        script: |
          fw ver
          cpstat -f all ha
          enabled_blades
        targets:
          - CL-DC1_A
          - CL-DC1_B
          - GW-Perimeter
        wait_for_task: true

    # 5) Re-install policy (CDT/CPUSE installs Access Control only — cover TP/QoS/Desktop)
    - name: Install the full policy package
      check_point.mgmt.cp_mgmt_install_policy:
        policy_package: Standard
        targets:
          - CL-DC1
          - GW-Perimeter
        access: true
        threat_prevention: true
        install_on_all_cluster_members_or_fail: true
        wait_for_task: true

    # 6) Publish the management session
    - name: Publish the session
      check_point.mgmt.cp_mgmt_publish:
```
Run it:
```bash
ansible-playbook -i inventory.ini deploy_cp.yml --ask-vault-pass
```
> **Requires Management R80.40+** (`method`/`package_location`/verify options need R81+). Great for pure API/CI-CD pipelines; but member-by-member failover is *your* responsibility via `cluster_delay` — the API does not do a Connectivity Upgrade for you the way CDT does.

#### Pattern 2 — Ansible triggers CDT over SSH (keeps CDT's native orchestration)

Here Ansible connects to the **Management Server over SSH** (Expert/UID-0 user) and simply drives CDT. Best when you need CDT's cluster/VSX/Maestro/Connectivity-Upgrade logic but want a pipeline to start it and collect results.
```yaml
---
- name: Orchestrate a CDT run from Ansible
  hosts: mgmt_servers            # SSH connection to the SMS (Expert-capable user)
  gather_facts: false
  vars:
    cdt: /opt/CPcdt/CentralDeploymentTool
    cand: /opt/CPcdt/CandidateListsRepository/cluster.csv
    plan: /opt/CPcdt/DeploymentPlanRepository/upgrade_cluster.xml
  tasks:
    - name: Fail fast if a CDT instance is already running
      ansible.builtin.command: pidof CentralDeploymentTool
      register: cdt_pid
      failed_when: cdt_pid.rc == 0     # rc==0 means a PID was found
      changed_when: false

    - name: Generate a fresh candidates list
      ansible.builtin.command: "{{ cdt }} -generate -candidates={{ cand }} -deploymentplan={{ plan }}"

    - name: Execute the deployment plan (long-running; don't let SSH time out)
      ansible.builtin.command: "{{ cdt }} -execute -candidates={{ cand }} -deploymentplan={{ plan }}"
      async: 10800                     # allow up to 3 hours
      poll: 60                         # check every 60s
      register: cdt_run

    - name: Retrieve the CDT status report
      ansible.builtin.fetch:
        src: /opt/CPcdt/CDT_status.txt
        dest: ./cdt_reports/
        flat: true
```
> **Gotcha:** for multi-hour upgrades use `async`/`poll` (above) so the SSH task isn't cut off. The SSH user must have Expert/UID-0. This pattern works on **any** supported CDT/Mgmt version (no R80.40 API requirement).

**Which pattern?** Use **Pattern 1** for API-native CI-CD where you accept manual staggering; use **Pattern 2** when you want CDT's zero-touch cluster failover / VSX / Maestro handling driven from a pipeline.

---

### 9.8 Use Case H — RMA backup & restore automation

**Scenario:** Standardize appliance replacement. CDT (`RmaTool` / RMA mode) centrally backs up gateway configuration and later restores it onto the replacement unit.

High-level flow (see the Admin Guide **RMA Mode** page for exact flags on your build):
1. **Generate** an RMA candidates list, or back up **all** gateways (no candidates file needed for a full backup).
2. **Collect RMA backup** — CDT stores each gateway's backup under `<repository_path>/backups/`.
3. **Restore** the backup onto the replacement appliance (optionally specifying a CPUSE Clean Install package).

> Reminder from limitations: before RMA restore, the appliance must have been up ≥ 8 minutes (uptime ≥ 480s); RMA backup is unsupported on VSX VSLS cluster members.

---

### 9.9 More scenario recipes (quick reference)

**a) VSX gateway / VSX cluster upgrade (Advanced mode)** — use the *same* plan as Use Case B; CDT handles the Virtual Systems and (for VSX clusters) the failover. Both VSX cluster members share **one** batch number.
```xml
<install_package path="/opt/CPcdt/packages/Check_Point_R82_T631_Fresh_Install_and_Upgrade.tgz" />
```
> **Gotchas:** back up the Management Server first; RMA backup is unsupported on VSX **VSLS** members; only Access Control policy is installed — install policy **per Virtual System** from SmartConsole if needed.

**b) Maestro Security Group upgrade** — supported for single-site and multi-site, **but NOT multi-site Active-Active**. CDT upgrades members by group order (Backup → Standby → Active) with automatic failover. Same `-generate` / `-execute` flow as a cluster; make sure every Security Group Member is eligible in the candidates list.

**c) Multi-Domain Server — upgrade several Domains in parallel** — one CDT process per Domain, each with its **own** candidate file:
```bash
# Domain A
mdsenv 10.1.1.10
nohup $CDTDIR/CentralDeploymentTool -execute \
  -candidates=/opt/CPcdt/CandidateListsRepository/domainA.csv \
  -deploymentplan=/opt/CPcdt/DeploymentPlanRepository/plan.xml -server=10.1.1.10 &

# Domain B (runs in parallel — different candidate file!)
mdsenv 10.1.1.20
nohup $CDTDIR/CentralDeploymentTool -execute \
  -candidates=/opt/CPcdt/CandidateListsRepository/domainB.csv \
  -deploymentplan=/opt/CPcdt/DeploymentPlanRepository/plan.xml -server=10.1.1.20 &
```

**d) Roll back / uninstall a Hotfix (Advanced mode)** — automated uninstall via CPUSE:
```xml
<!-- filename = the package FILE name only, NOT a full path -->
<uninstall_cpuse_package filename="Check_Point_R82_JUMBO_HF_T30_FULL.tgz" />
<reboot />
```
Ansible equivalent: `check_point.mgmt.cp_mgmt_uninstall_software_package` (params: `name`, `targets`, `concurrency_limit`, `cluster_installation_settings`).
> **Note:** rolling back a *major upgrade* means reverting the Gaia **snapshot** you took with `create_snapshot` — snapshot revert is a **manual Gaia step**, not a CDT action. Always snapshot before a major upgrade.

**e) Push a config/hotfix file to many gateways (no install)** — pure fleet file distribution:
```xml
<push_file local_path="/opt/CPcdt/files/syslog.conf" remote_path="/etc/syslog.conf" />
<execute_command command="service syslog restart" />
```

**f) Run a command / collect a file fleet-wide (audit, no downtime)**:
```xml
<execute_command command="cpstat os -f cpu" />
<pull_file remote_path="/var/log/messages" local_dir="/opt/CPcdt/collected/" iscritical="false" />
```
> **Gotcha:** `execute_command` does not allow shell special characters (`>`, `|`, `*`, …). For anything complex, ship a script and use `execute_script` instead.

**g) Pre-seed a package over a slow link** — manually copy the package to `/var/log/upload/` on the gateway; on the next CDT install, CDT verifies the MD5, **skips the transfer**, and proceeds straight to import/install.

---

## 10. Best Practices for Automating with CDT

1. **Pre-stage with Preparations mode** before the maintenance window to minimize downtime.
2. **Always run with `nohup`** (or a task scheduler outside Gaia cron) so SSH disconnects don't abort the job.
3. **Use a filter file** on large databases to speed up Candidates List generation (`-filter=<file>`).
4. **Wrap CDT in a Bash script** for pre/post management-server actions (CDT is blocking, so sequencing is reliable).
5. **Use Clish + RBAC** (`cdt` feature, Read/Write) to let operators run upgrades without Expert passwords.
6. **Use `session <name>`** (v1.9.8+) or per-Domain execution on MDS to run multiple deployments concurrently.
7. **Plan manual policy installs** (Threat Prevention/QoS/Desktop) post-upgrade.
8. **Enable DEBUG logging** (`FileLevel="DEBUG"` in the XML) when troubleshooting; logs are in `/var/log/CPcdt/` (server) and `/opt/CPInstLog/` (gateway).
9. **Pre-copy packages** to `/var/log/upload/` on gateways over limited-bandwidth links — CDT detects and skips the transfer.
10. **Test user scripts standalone** first; ensure no direct reboot (use exit code `222` to have CDT reboot).

---

## 11. Troubleshooting Quick Reference

- **Version check:** `$CDTDIR/CentralDeploymentTool -v` or `cpvinfo /path/CentralDeploymentTool | grep -E "Build Number|Minor Release"`
- **Enable debug:** set `<Logging FileLevel="DEBUG" ...>` in `CentralDeploymentTool.xml`.
- **Logs to collect (server):** Candidates List, `CDT_status.txt`, `/var/log/CPcdt/`, `/var/log/CPda/`, CPInfo.
- **Logs to collect (gateway):** `/opt/CPInstLog/`, `/var/log/message*`, CPInfo.
- **Stuck process ("cannot run multiple instances"):** `pidof CentralDeploymentTool` → `kill -9 <PID>`.
- **Cluster validation errors:** ensure cluster is stable (Active/Standby or Master/Backup) before running.
- **Common licensing failure:** verify with `cplic print` (valid license + support contract + contract file on target).

---

## 12. Key References

- **sk111158** — Central Deployment Tool (CDT) main article (downloads, FAQ, limitations, troubleshooting).
- **CDT Administration Guide** — https://sc1.checkpoint.com/documents/CDT/Unified/Default.htm
  - Introduction to CDT — https://sc1.checkpoint.com/documents/CDT/Unified/Topics/Introduction-to-CDT.htm
  - CDT in Gaia Clish — https://sc1.checkpoint.com/documents/CDT/Unified/Topics/CDT-in-Gaia-Clish.htm
- **sk92449** — CPUSE / Gaia Deployment Agent.
- **sk181606** — CloudGuard Network Security Clusters upgrade using CDT.
- **sk144112** — Gaia Dynamic CLI (required for Clish integration).
- **Ansible module** — `check_point.mgmt.cp_mgmt_install_software_package`
  https://docs.ansible.com/projects/ansible/latest/collections/check_point/mgmt/cp_mgmt_install_software_package_module.html
- **Ansible collection repo** — https://github.com/CheckPointSW/CheckPointAnsibleMgmtCollection

---
