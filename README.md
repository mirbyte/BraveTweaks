# BraveTweaks

BraveTweaks is a small Windows 11 utility for making a normal Brave installation behave as close as practical to Brave Origin.

Apply, Remove managed policies, and Restore require an explicit action. No registry changes are made when the GUI starts. Origin preset checks Origin's default-off feature and telemetry policies from brave-core; it does not apply them by itself.

## Current state

Toggles load matching policies from the selected registry scope. Origin preset is sourced from `BraveOriginPrefMetadata` in brave-core (Rewards, Wallet, VPN, Leo, local AI, News, Talk, Playlist, Speedreader, Wayback, Tor, Web Discovery, email aliases, P3A, usage ping). Chromium `MetricsReportingEnabled` and `BackgroundModeEnabled`, Safe Browsing reporting, URL-keyed data collection, critical-only Griffin variations, and enhanced spell check are optional extras and are not part of that preset. Critical-only variations preserve emergency security and stability fixes. Enhanced spell check can be disabled while offline spell checking remains available. Advanced hardening controls cover WebRTC IP handling, dynamic browser code, and application-bound encryption.

Brave-specific policy names match the 1.94 ADMX templates. Exact UI parity with Origin still depends on applying and checking `brave://policy`.

## Related project

[SlimBrave Neo](https://github.com/ChaoticSi1ence/SlimBrave-Neo) is a broader, cross-platform project for Linux, macOS, and Windows. It provides a larger policy catalog, more presets, CLI and TUI workflows. Its broader scope is useful for extensive policy management, but it requires more decisions and policy knowledge.

BraveTweaks has a narrower focus: a beginner-friendly Windows 11 GUI for applying the policy-controlled part of Brave Origin's debloating to a regular Brave installation. It also exposes selected advanced policies that are not easy to find in Brave settings. BraveTweaks cannot reproduce Origin features that are compiled out of the Origin browser or have no policy equivalent.

## Requirements

- Windows 11
- Python 3.10 or newer
- PySide6, if using the desktop interface
- Brave installed for detection, unless policies are being staged for a future
  installation or the goal is only to inspect or restore registry values
- Portapps Brave is supported for both User (HKCU) and Machine (HKLM) policies;
  selecting its portable `brave.exe` is optional

Run from source with `main.pyw`. A PyInstaller exe will be added later.

The default user-scope policy key is:

```text
HKEY_CURRENT_USER\Software\Policies\BraveSoftware\Brave
```

Brave Origin is detected when present and is not an apply target. Both products read `Software\Policies\BraveSoftware\Brave`, so Apply also manages Origin. If regular Brave is detected, Apply manages its policy state. If no regular Brave is detected and Brave Origin is not installed, Apply stages a non-empty policy state for a future Brave installation. Origin-only installations remain blocked because both products read the same policy hive. Resetting or removing managed policies does not require Brave.

Machine scope requires an elevated process. Some Windows 11 installs also lock `HKCU\Software\Policies` to Administrators, so User scope Apply needs elevation too. Both policy scopes have been verified with Portapps Brave. Other portable wrappers are not specifically verified. The executable path is only needed for detection and version reporting; registry policy operations do not require it.

## Existing registry policy files

If a legacy `.reg` file previously configured Brave under `HKLM`, select Machine scope to manage those values. Verify and Apply mention Brave policy values found in the other scope. Known legacy values are recognized, while unknown values are reported and left untouched.

## Usage

Install the dependency once:

```console
pip install -r requirements.txt
```

Then double-click `main.pyw` in Windows Explorer. No command-line parameters are required or used.

Origin preset selects Origin's default-off set. Apply, Verify, and Restore require an explicit click. Apply reconciles the checked policy state: checked policies are set and unchecked managed policies are removed. With no policies selected, Apply opens the confirmed managed-policy reset flow. Remove managed policies deletes only known BraveTweaks policy values from the selected scope after confirmation and creates a backup first. Unknown values are left untouched.

## Backups and restore

Before an apply or managed-policy cleanup, the tool writes a JSON backup under the application's `backups` directory. The GUI's Restore Backup button can restore one of these files.

The backup records the policy key, scope, existing values, and operation-specific metadata. Restore only accepts a backup for the same policy scope and key.

## Project layout

```text
BraveTweaks/
  main.pyw
  requirements.txt
  README.md
  src/
    bravetweaks/
      __init__.py
      gui.py         # PySide6 desktop interface
      brave.py       # Brave executable detection and version probe hook
      config.py      # Local paths and registry scope configuration
      policies.py    # Small curated policy definitions
      profile.py     # Origin profile planning, application, and verification
      registry.py    # Windows registry read, write, backup, and restore
```

## Trademark and affiliation

BraveTweaks is an independent, unofficial project. It is not affiliated with, associated with, authorized by, endorsed by, or officially connected to Brave Software, Inc. or its subsidiaries and affiliates.

“Brave” and related names, marks, logos, and emblems are trademarks of their respective owners. The official Brave website is https://brave.com/.


---


