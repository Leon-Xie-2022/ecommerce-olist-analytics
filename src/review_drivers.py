"""Low-review driver analysis: logistic regression of a 1-2 star review on delivery outcome and controls.

The raw comparison (sql/metrics/06) shows late orders get far more low reviews. Late orders are also
concentrated in certain states, categories and months, so this model asks whether the gap remains
after holding those constant. It measures an adjusted association, not a causal effect.

Outputs
    reports/tables/review_drivers_adjusted_rates.csv   raw vs model-adjusted low-review rate per bucket
    reports/tables/review_drivers_odds_ratios.csv      odds ratios with 95% CI for the main terms
    reports/figures/review_drivers.png                 raw vs adjusted rates

Run after src/build_db.py:  python src/review_drivers.py
"""
import sys

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from config import DB_PATH, FIGURES_DIR, REPORTS_DIR, SQL_DIR

REFERENCE_BUCKET = "2. 1-9 days early"  # the typical experience (28% of orders) is the baseline
FORMULA = (
    "low_review ~ C(delivery_bucket, Treatment(reference='" + REFERENCE_BUCKET + "'))"
    " + promised_days + C(items_band) + multi_seller + log_product_value + freight_ratio"
    " + C(customer_state, Treatment(reference='SP')) + C(main_category) + C(purchase_month)"
)
BLUE, ORANGE = "#2a78d6", "#eb6834"  # reference palette slots 1-2
INK, MUTED, GRID = "#0b0b0b", "#5f5e5a", "#e4e3df"


def load_data():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.sql((SQL_DIR / "models" / "review_model_data.sql").read_text(encoding="utf-8")).df()
    con.close()
    return df


def adjusted_rates(model, df):
    """Average predicted low-review rate if every order had the given delivery bucket,
    keeping all other characteristics as observed (counterfactual standardisation)."""
    rows = []
    for bucket in sorted(df["delivery_bucket"].unique()):
        scenario = df.assign(delivery_bucket=bucket)
        rows.append({
            "delivery_bucket": bucket,
            "orders": int((df["delivery_bucket"] == bucket).sum()),
            "raw_low_review_pct": round(100 * df.loc[df["delivery_bucket"] == bucket, "low_review"].mean(), 1),
            "adjusted_low_review_pct": round(100 * model.predict(scenario).mean(), 1),
        })
    return pd.DataFrame(rows)


def odds_ratios(model):
    table = pd.DataFrame({
        "odds_ratio": np.exp(model.params),
        "ci_low": np.exp(model.conf_int()[0]),
        "ci_high": np.exp(model.conf_int()[1]),
        "p_value": model.pvalues,
    })
    keep = table.index.str.contains("delivery_bucket|items_band|multi_seller|promised_days|freight_ratio"
                                    "|log_product_value")
    table = table[keep].round(3)
    table.index = (table.index.str.replace(r"C\(delivery_bucket.*\)\[T\.", "delivery: ", regex=True)
                               .str.replace(r"C\(items_band\)\[T\.", "items: ", regex=True)
                               .str.replace("]", "", regex=False))
    return table.rename_axis("term").reset_index()


def plot(rates, path):
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)
    x = np.arange(len(rates))
    width = 0.38
    labels = [b.split(". ", 1)[1] for b in rates["delivery_bucket"]]
    for offset, column, color, name in [(-width / 2, "raw_low_review_pct", BLUE, "Raw rate"),
                                        (width / 2, "adjusted_low_review_pct", ORANGE,
                                         "Adjusted for state, category, month, basket")]:
        bars = ax.bar(x + offset, rates[column], width - 0.03, color=color, label=name)
        for bar, value in zip(bars, rates[column]):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 1, f"{value:.0f}%",
                    ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_xticks(x, labels, fontsize=9, color=INK)
    ax.set_ylabel("Orders with a 1-2 star review (%)", fontsize=9, color=MUTED)
    ax.set_ylim(0, max(rates[["raw_low_review_pct", "adjusted_low_review_pct"]].max()) * 1.15)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", colors=MUTED, labelsize=8, length=0)
    ax.tick_params(axis="x", length=0)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("Low-review rate by delivery outcome: raw vs adjusted (association, not causation)",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    df = load_data()
    model = smf.logit(FORMULA, data=df).fit(disp=False, cov_type="HC1")

    rates = adjusted_rates(model, df)
    ors = odds_ratios(model)
    (REPORTS_DIR / "tables").mkdir(parents=True, exist_ok=True)
    rates.to_csv(REPORTS_DIR / "tables" / "review_drivers_adjusted_rates.csv", index=False)
    ors.to_csv(REPORTS_DIR / "tables" / "review_drivers_odds_ratios.csv", index=False)
    plot(rates, FIGURES_DIR / "review_drivers.png")

    print(f"orders: {len(df):,}   low-review share: {df['low_review'].mean():.1%}   "
          f"McFadden pseudo R2: {model.prsquared:.3f}")
    print("\n" + rates.to_string(index=False))
    print("\n" + ors.to_string(index=False))


if __name__ == "__main__":
    main()
