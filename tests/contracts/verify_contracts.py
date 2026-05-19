"""Contract manifest and registry verification script.

Verifies all registered ports can be resolved and generates a contract manifest.
对应 AC-7: verify_contracts.py 增强覆盖全部已注册端口
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


def verify_all_ports_resolvable() -> list[str]:
    """Verify all registered ports can be resolved by Resolver.

    Returns:
        List of error messages for ports that failed to resolve
    """
    issues = []
    resolver = Resolver()

    for spec in _global_registry.list_all():
        try:
            instance = resolver.resolve(spec.name)
            print(f"[OK] {spec.name}: {type(instance).__name__}")
        except Exception as e:
            issues.append(f"[FAIL] {spec.name}: {e}")
            print(f"[FAIL] {spec.name}: {e}")

    return issues


if __name__ == "__main__":
    print("=" * 60)
    print("Contract Registry Verification")
    print("=" * 60)

    # Bootstrap registry
    bootstrap()

    # Generate manifest
    manifest = generate_contract_manifest()
    print(f"\nTotal registered ports: {len(manifest)}\n")

    for item in sorted(manifest, key=lambda x: x["name"]):
        print(f"  {item['name']:<30} {item['interface']:<35} {item['module']}")

    print("\n" + "=" * 60)
    print("Verify All Ports Resolvable")
    print("=" * 60)
    issues = verify_all_ports_resolvable()
    if issues:
        print("\nResolution failures:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\nAll registered ports resolved successfully!")

    print("\n" + "=" * 60)
    print("Contract Manifest (JSON)")
    print("=" * 60)
    import json

    print(json.dumps(manifest, indent=2, default=str))
