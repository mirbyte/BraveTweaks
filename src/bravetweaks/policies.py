from __future__ import annotations

from dataclasses import dataclass
from typing import Union


PolicyValue = Union[bool, int, str]

CATEGORY_TITLES = {
    "features": "Origin features",
    "telemetry": "Telemetry",
    "optional": "Optional Chromium policies",
    "hardening": "Advanced hardening",
}


@dataclass(frozen=True)
class PolicyDefinition:
    name: str
    value: PolicyValue
    label: str
    description: str
    category: str
    origin_preset: bool = False
    min_version: str | None = None
    legacy_values: tuple[tuple[str, PolicyValue], ...] = ()


# Origin defaults from brave-core BraveOriginPrefMetadata
# (browser/brave_origin/brave_origin_service_factory.cc).
POLICIES: tuple[PolicyDefinition, ...] = (
    PolicyDefinition(
        name="BraveRewardsDisabled",
        value=True,
        label="Disable Rewards",
        description="Origin default: Rewards compiled out / disabled by policy.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveWalletDisabled",
        value=True,
        label="Disable Wallet",
        description="Origin default: Wallet disabled by policy.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveVPNDisabled",
        value=True,
        label="Disable VPN",
        description="Origin default: VPN disabled by policy.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveAIChatEnabled",
        value=False,
        label="Disable Leo / AI chat",
        description="Origin default: AI chat disabled by policy.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveLocalAIEnabled",
        value=False,
        label="Disable on-device AI",
        description="Origin default: local AI master switch off.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveNewsDisabled",
        value=True,
        label="Disable News",
        description="Origin default: News disabled by policy.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveTalkDisabled",
        value=True,
        label="Disable Talk",
        description="Origin default: Talk disabled by policy.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BravePlaylistEnabled",
        value=False,
        label="Disable Playlist",
        description="Origin default: Playlist off.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveSpeedreaderEnabled",
        value=False,
        label="Disable Speedreader",
        description="Origin default: Speedreader off.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveWaybackMachineEnabled",
        value=False,
        label="Disable Wayback Machine",
        description="Origin default: Wayback Machine off.",
        category="features",
        origin_preset=True,
        legacy_values=(("BraveWaybackMachineDisabled", True),),
    ),
    PolicyDefinition(
        name="TorDisabled",
        value=True,
        label="Disable Tor windows",
        description="Origin default: Tor disabled by policy.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveWebDiscoveryEnabled",
        value=False,
        label="Disable Web Discovery",
        description="Origin default: Web Discovery off.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="EmailAliasesEnabled",
        value=False,
        label="Disable email aliases",
        description="Origin default: email aliases off.",
        category="features",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="SafeBrowsingExtendedReportingEnabled",
        value=False,
        label="Disable Safe Browsing Reporting",
        description=(
            "Stops extended Safe Browsing reports, such as details about "
            "suspicious pages and downloads, from being sent to Google. "
            "Safe Browsing protection remains enabled."
        ),
        category="telemetry",
    ),
    PolicyDefinition(
        name="UrlKeyedAnonymizedDataCollectionEnabled",
        value=False,
        label="Disable URL Data Collection",
        description=(
            "Stops URL-keyed anonymized data collection, which can report "
            "visited URLs to improve suggestions and safety features."
        ),
        category="telemetry",
    ),
    PolicyDefinition(
        name="BraveP3AEnabled",
        value=False,
        label="Disable P3A",
        description="Origin default: P3A off.",
        category="telemetry",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="BraveStatsPingEnabled",
        value=False,
        label="Disable usage ping",
        description="Origin default: stats reporting off.",
        category="telemetry",
        origin_preset=True,
    ),
    PolicyDefinition(
        name="MetricsReportingEnabled",
        value=False,
        label="Disable Chromium metrics",
        description=(
            "Benefit: disables Chromium usage metrics and crash-related "
            "reporting. This does not disable browser features or affect "
            "normal browsing. Brave-specific P3A and stats reporting are "
            "controlled by separate policies."
        ),
        category="optional",
    ),
    PolicyDefinition(
        name="BackgroundModeEnabled",
        value=False,
        label="Disable background mode",
        description=(
            "Benefit: lets Brave exit fully after its windows are closed "
            "instead of remaining active for background apps and extensions. "
            "Tradeoff: background extension tasks, web-app activity, and "
            "related notifications may stop. It does not disable Brave's "
            "updater."
        ),
        category="optional",
    ),
    PolicyDefinition(
        name="ChromeVariations",
        value=1,
        label="Limit Variations to Critical Fixes",
        description=(
            "Restricts Brave's remote experiment seed, Griffin, to critical "
            "security and stability fixes instead of the full set of A/B "
            "experiments. Emergency feature kill switches remain available."
        ),
        category="optional",
    ),
    PolicyDefinition(
        name="SpellCheckServiceEnabled",
        value=False,
        label="Disable Enhanced Spell Check",
        description=(
            "Stops enhanced spell check from sending text typed into web "
            "forms to Google's servers. Offline spell checking remains "
            "available."
        ),
        category="optional",
    ),
    PolicyDefinition(
        name="WebRtcIPHandling",
        value="default_public_interface_only",
        label="Restrict WebRTC IP exposure",
        description=(
            "Benefit: WebRTC will not advertise private or LAN IP addresses, "
            "reducing local-network exposure and network fingerprinting. "
            "Tradeoff: calls between devices on the same network may lose "
            "their direct path and use a relay or fail; VPN calls may use a "
            "different interface. This affects WebRTC calls and screen-sharing "
            "transport, not ordinary browsing."
        ),
        category="hardening",
    ),
    PolicyDefinition(
        name="DynamicCodeSettings",
        value=1,
        label="Prevent dynamic browser code",
        description=(
            "Benefit: prevents the Brave browser process from creating dynamic "
            "code, reducing the process-injection surface and strengthening "
            "browser integrity. Tradeoff: software that injects code into "
            "Brave, such as some antivirus, printer, accessibility, or overlay "
            "tools, may fail to load or stop working. It does not disable "
            "webpage JavaScript or extensions."
        ),
        category="hardening",
    ),
    PolicyDefinition(
        name="ApplicationBoundEncryptionEnabled",
        value=True,
        label="Enforce application-bound encryption",
        description=(
            "Benefit: binds local browser-data encryption keys to Brave where "
            "supported, making cookies, passwords, and tokens harder for other "
            "apps to decrypt. Tradeoff: copied profiles may not decrypt on "
            "another installation, and external tools that read Brave's "
            "encrypted data may stop working. Normal browsing is unaffected. "
            "Normally enabled by default."
        ),
        category="hardening",
    ),
)


def all_policies() -> tuple[PolicyDefinition, ...]:
    return POLICIES


def origin_preset_policies() -> tuple[PolicyDefinition, ...]:
    return tuple(policy for policy in POLICIES if policy.origin_preset)
