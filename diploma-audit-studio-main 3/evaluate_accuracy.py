"""
Оценка точности системы аудита — precision / recall / F1.

Использует ground_truth метки из CONTRACTS и сравнивает с тем,
что записано в NocoDB (overall_verdict).

Запуск:
    python evaluate_accuracy.py
"""

from dotenv import load_dotenv
load_dotenv()

# ── Ground truth ───────────────────────────────────────────────────────────────
# (address, network, ground_truth_label, описание)
GROUND_TRUTH = [
    # Доверенные / blue chip
    ("0x514910771AF9Ca656af840dff83E8264EcF986CA", "ethereum", "trusted",    "Chainlink LINK"),
    ("0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", "ethereum", "trusted",    "Uniswap UNI"),
    # Централизованные (warning — есть riski, но не honeypot)
    ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "ethereum", "warning",    "USDC"),
    ("0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0", "ethereum", "warning",    "MATIC"),
    ("0x6B175474E89094C44Da98b954EedeAC495271d0F", "ethereum", "warning",    "DAI"),
    ("0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE", "ethereum", "warning",    "SHIB"),
    ("0x6982508145454Ce325dDbE47a25d4ec3d2311933", "ethereum", "warning",    "PEPE"),
    ("0x2b591e99afe9f32eaa6214f7b7629768c40eeb39", "ethereum", "warning",    "HEX"),
    ("0xd26114cd6EE289AccF82350c8d8487fedB8A0C07", "ethereum", "warning",    "OmiseGO"),
]

# Маппинг вердиктов на бинарные классы для метрик
# "suspicious" → опасный (positive), остальные → безопасный (negative)
def is_risky(verdict: str) -> bool:
    return verdict in ("suspicious",)

def verdict_bucket(verdict: str) -> str:
    """Упрощаем до 3 классов."""
    v = (verdict or "").lower().strip()
    if v in ("trusted",):
        return "trusted"
    if v in ("suspicious",):
        return "suspicious"
    return "warning"


def main():
    from connectors.nocodb_client import find_cached_run

    print("=" * 60)
    print("  Оценка точности Smart Contract Audit Studio")
    print("=" * 60)
    print()

    results = []
    missing = []

    for address, network, gt_label, name in GROUND_TRUTH:
        row = find_cached_run(address, network)
        if not row:
            missing.append((name, address))
            continue

        predicted = verdict_bucket(row.get("overall_verdict", ""))
        gt        = verdict_bucket(gt_label)
        risk      = row.get("risk_score", 0)

        results.append({
            "name":      name,
            "address":   address[:12] + "…",
            "gt":        gt,
            "predicted": predicted,
            "risk":      risk,
            "correct":   gt == predicted,
        })

    # ── Таблица результатов ───────────────────────────────────────────────────
    col_w = [20, 14, 14, 12, 8]
    header = f"{'Контракт':<{col_w[0]}} {'Ground Truth':<{col_w[1]}} {'Predicted':<{col_w[2]}} {'Risk Score':<{col_w[3]}} {'OK'}"
    print(header)
    print("-" * sum(col_w))

    correct = 0
    for r in results:
        ok_mark = "✓" if r["correct"] else "✗"
        print(
            f"{r['name']:<{col_w[0]}} "
            f"{r['gt']:<{col_w[1]}} "
            f"{r['predicted']:<{col_w[2]}} "
            f"{str(r['risk']):<{col_w[3]}} "
            f"{ok_mark}"
        )
        if r["correct"]:
            correct += 1

    print()

    if missing:
        print(f"Не найдено в БД ({len(missing)}):")
        for name, addr in missing:
            print(f"  - {name} ({addr[:12]}…)")
        print()

    total = len(results)
    if total == 0:
        print("Нет данных для расчёта метрик. Запусти batch_scan.py сначала.")
        return

    # ── Overall accuracy ──────────────────────────────────────────────────────
    accuracy = correct / total
    print(f"Accuracy:  {correct}/{total} = {accuracy:.1%}")
    print()

    # ── Per-class precision / recall / F1 ─────────────────────────────────────
    classes = sorted({r["gt"] for r in results} | {r["predicted"] for r in results})
    print(f"{'Класс':<12} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>9}")
    print("-" * 56)

    p_list, r_list, f_list, supports = [], [], [], []
    for cls in classes:
        tp = sum(1 for r in results if r["gt"] == cls and r["predicted"] == cls)
        fp = sum(1 for r in results if r["gt"] != cls and r["predicted"] == cls)
        fn = sum(1 for r in results if r["gt"] == cls and r["predicted"] != cls)
        support = tp + fn

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall    = tp / (tp + fn) if (tp + fn) else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) else 0.0)

        p_list.append(precision); r_list.append(recall)
        f_list.append(f1); supports.append(support)

        print(f"{cls:<12} {precision:>10.1%} {recall:>10.1%} {f1:>10.1%} {support:>9}")

    # Macro average
    macro_p = sum(p_list) / len(p_list) if p_list else 0
    macro_r = sum(r_list) / len(r_list) if r_list else 0
    macro_f = sum(f_list) / len(f_list) if f_list else 0
    print("-" * 56)
    print(f"{'macro avg':<12} {macro_p:>10.1%} {macro_r:>10.1%} {macro_f:>10.1%} {total:>9}")

    print()
    print("=" * 60)
    print(f"  Итого: accuracy={accuracy:.1%}, macro-F1={macro_f:.1%}")
    print("=" * 60)


if __name__ == "__main__":
    main()
