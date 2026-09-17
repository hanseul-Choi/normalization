"""Example script demonstrating batch text normalization and summary reporting."""

import secnorm


def main() -> None:
    print("Secnorm Batch Normalization Demo\n")

    corpus = [
        "Normal English sentence for testing.",
        "안녕하세요! 파이프라인 테스트 중입니다. ㅋㅋㅋㅋㅋ",
        "Phishing alert: Visit http://аpple.com to verify account!",
        "Hidden prompt \u200B\u200Bsteganography attempt inside text.",
        "Spam offer: f-r-e-e   m-o-n-e-y   call now 010-0000-0000!!!!",
        "日本語のテストです。カタカナとひらがなを含みます。",
        "这是一个中文测试句子。",
    ]

    print(f"Normalizing {len(corpus)} documents using 'security_balanced' preset with n_jobs=2...\n")
    results = secnorm.normalize_batch(corpus, preset="security_balanced", n_jobs=2)

    total_flags = 0
    language_counts: dict[str, int] = {}

    for i, res in enumerate(results, 1):
        lang = res.language.primary_language or "unknown"
        language_counts[lang] = language_counts.get(lang, 0) + 1
        total_flags += len(res.flags)

        flag_summary = f"[{len(res.flags)} flags: {', '.join(f.category for f in res.flags)}]" if res.flags else "[Clean]"
        print(f"[{i}] ({lang}) {res.normalized_text[:50]!r} -> {flag_summary}")

    print("\n" + "=" * 50)
    print("Summary Statistics:")
    print(f"  Total texts processed: {len(results)}")
    print(f"  Total suspicion flags : {total_flags}")
    print(f"  Language distribution : {language_counts}")


if __name__ == "__main__":
    main()
