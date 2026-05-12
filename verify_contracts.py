"""Contract manifest and registry verification script.

This script generates the contract manifest (task 1.5.5) and verifies:
- task 2.4.4: Deprecated ports (VectorStorage etc.) are not registered
- task 2.4.5: Resolver can correctly resolve known ports
"""

from __future__ import annotations

from src.composition_root import bootstrap
from src.domain.ports.registry import _global_registry
from src.domain.ports.resolver import Resolver


def generate_contract_manifest() -> list[dict]:
    """Generate contract manifest with name/interface/path/source."""
    manifest = []
    for spec in _global_registry.list_all():
        manifest.append(
            {
                "name": spec.name,
                "interface": spec.interface.__name__ if hasattr(spec.interface, "__name__") else str(spec.interface),
                "impl": spec.impl if isinstance(spec.impl, str) else spec.impl.__name__,
                "module": spec.module,
                "lifetime": spec.lifetime.value,
                "deprecated": spec.deprecated,
            }
        )
    return manifest


def verify_deprecated_ports_not_registered() -> list[str]:
    """Verify deprecated ports (VectorStorage etc.) are not registered."""
    issues = []

    # VectorStorage ABC should NOT be registered (deprecated)
    if "VectorStorage" in [spec.name for spec in _global_registry.list_all()]:
        issues.append("VectorStorage should not be registered (deprecated)")
    else:
        print("[OK] VectorStorage ABC not registered (deprecated)")

    # l3_vector should NOT be registered (pending migration)
    if "l3_vector" in [spec.name for spec in _global_registry.list_all()]:
        issues.append("l3_vector should not be registered (pending migration)")
    else:
        print("[OK] l3_vector not registered (pending migration)")

    return issues


def verify_resolver_works() -> list[str]:
    """Verify resolver can correctly resolve known ports."""
    issues = []
    resolver = Resolver()

    # Ports that should be resolvable
    resolvable_ports = [
        "event_publisher",
        "outbox_repo",
        "hash_router",
        "semantic_router",
        "user_repo",
    ]

    for port_name in resolvable_ports:
        try:
            instance = resolver.resolve(port_name)
            print(f"[OK] Resolved {port_name}: {type(instance).__name__}")
        except Exception as e:
            issues.append(f"Failed to resolve {port_name}: {e}")

    return issues


if __name__ == "__main__":
    print("=" * 60)
    print("Contract Manifest Generation (Task 1.5.5)")
    print("=" * 60)

    # Bootstrap registry
    bootstrap()

    # Generate manifest
    manifest = generate_contract_manifest()
    print(f"\nTotal registered ports: {len(manifest)}\n")

    for item in sorted(manifest, key=lambda x: x["name"]):
        print(f"  {item['name']:<30} {item['interface']:<35} {item['module']}")

    print("\n" + "=" * 60)
    print("Verify Deprecated Ports Not Registered (Task 2.4.4)")
    print("=" * 60)
    issues = verify_deprecated_ports_not_registered()
    if issues:
        for issue in issues:
            print(f"[FAIL] {issue}")
    else:
        print("\nAll deprecated port checks passed!")

    print("\n" + "=" * 60)
    print("Verify Resolver Works (Task 2.4.5)")
    print("=" * 60)
    issues = verify_resolver_works()
    if issues:
        for issue in issues:
            print(f"[FAIL] {issue}")
    else:
        print("\nAll resolver checks passed!")
