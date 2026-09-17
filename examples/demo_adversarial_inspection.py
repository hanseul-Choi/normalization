"""Example script demonstrating security inspection of adversarial and obfuscated inputs."""

import secnorm


def inspect_text(title: str, text: str, preset: str = "security_balanced") -> None:
    print("=" * 60)
    print(f"[{title}]")
    print(f"Input text : {text!r}")
    result = secnorm.normalize(text, preset=preset)
    print(f"Normalized : {result.normalized_text!r}")

    if result.normalized_variants:
        print(f"Variants   : {result.normalized_variants}")

    print(f"Language   : {result.language.primary_language} (confidence: {result.language.confidence if hasattr(result.language, 'confidence') else result.language.language_confidence:.2f})")
    print(f"Scripts    : {result.language.script_ratios}")

    if result.flags:
        print("Suspicion Flags:")
        for flag in result.flags:
            print(f"  - [{flag.severity.upper()}] {flag.category}: {flag.detail} (at raw span {flag.span})")
    else:
        print("Suspicion Flags: None")

    if result.transformations:
        print(f"Transformations applied ({len(result.transformations)}):")
        for t in result.transformations:
            print(f"  - [{t.step}] {t.rule}: {t.original!r} -> {t.replacement!r}")
    print()


def main() -> None:
    print("Secnorm Adversarial Inspection Demo\n")

    # 1. Homoglyph spoofing
    inspect_text("1. Homoglyph Domain Spoofing", "Check out https://аpple.com for deals!")

    # 2. Zero-width character steganography
    inspect_text("2. Zero-Width Char Injection", "Important\u200Bsecret\u200Cmessage")

    # 3. Bidi override Trojan Source pattern
    inspect_text("3. Bidi Override Attack", "Access granted to user: \u202eadmin\u202c")

    # 4. Separator injection and leetspeak
    inspect_text("4. Separator & Leetspeak Spam", "f.r.e.e   m.0.n.e.y   now!!!")

    # 5. Base64 payload detection & recursive normalization (security_strict preset)
    inspect_text(
        "5. Base64 Encoded Payload (Strict Preset)",
        "Payload: aHR0cHM6Ly9ldmlsLmNvbQ==",
        preset="security_strict",
    )


if __name__ == "__main__":
    main()
