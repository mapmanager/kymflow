import pandas as pd
from scipy import stats


def load_data():
    path = '/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v3-analysis/cudmore_stalls/file_table_n_7.csv'
    path = '/Users/cudmore/Dropbox/data/declan/2026/compare-condiitons/v3-analysis/cudmore_stalls/file_table_n_10.csv'
    df = pd.read_csv(path)
    return df

def run():
    df = load_data()

    # --- Filtering ---
    n_total = len(df)
    n_rejected = (df['Accepted'] == False).sum()  # noqa: E712
    df = df[df['Accepted'] == True]  # noqa: E712
    n_accepted = len(df)

    print("=" * 60)
    print("USER EVENT COMPARISON: Control vs AngII")
    print("=" * 60)
    print("\nFiltering (Accepted == True):")
    print(f"  Total rows:        {n_total}")
    print(f"  Accepted (used):   {n_accepted}")
    print(f"  Rejected (excl.):  {n_rejected}")

    conditions = sorted(df['Condition'].unique())
    if len(conditions) != 2:
        print(f"\nWARNING: Expected 2 conditions, found {conditions}")
        return

    # --- Per-file stats (for Mann-Whitney U) ---
    control = df.loc[df['Condition'] == 'Control', 'User Event']
    angii = df.loc[df['Condition'] == 'AngII', 'User Event']

    print("\n--- Version 1: Per-file (User Event per file) ---")
    print(f"  Control:  n={len(control)}")
    print(f"  AngII:    n={len(angii)}")
    print(f"\n  Control:  mean ± SD = {control.mean():.3f} ± {control.std():.3f}")
    print(f"  AngII:    mean ± SD = {angii.mean():.3f} ± {angii.std():.3f}")
    print(f"\n  Control:  median (IQR) = {control.median():.2f} ({control.quantile(0.25):.2f}–{control.quantile(0.75):.2f})")
    print(f"  AngII:    median (IQR) = {angii.median():.2f} ({angii.quantile(0.25):.2f}–{angii.quantile(0.75):.2f})")

    u_stat, p_value = stats.mannwhitneyu(control, angii, alternative='two-sided')
    print("\n  Mann-Whitney U test (two-sided):")
    print("    H0: The distributions of User Event per file are the same in Control and AngII.")
    print(f"    U statistic: {u_stat:.2f}")
    print(f"    p-value:     {p_value:.4f}")

    # --- Version 2: Total per condition ---
    total_control = control.sum()
    total_angii = angii.sum()
    print("\n--- Version 2: Total User Event per condition ---")
    print(f"  Control:  total = {total_control}  (n={len(control)} files)")
    print(f"  AngII:    total = {total_angii}  (n={len(angii)} files)")
    print("\n  Note: Mann-Whitney U above compares per-file counts; total per condition is descriptive only.")

    print("\n" + "=" * 60)

def summary():
    df = load_data()
    df = df[df['Accepted'] == True]  # noqa: E712

    treatments = df['Treatment'].unique()
    n_treatments = len(treatments)

    print("\n" + "=" * 60)
    print(f"SUMMARY BY TREATMENT (n={n_treatments} treatments)")
    print("=" * 60)

    # --- 1. User Event per file by Treatment ---
    print("\n--- User Event per file (by Treatment) ---")
    for t in treatments:
        s = df.loc[df['Treatment'] == t, 'User Event']
        print(f"  {t}:  n={len(s):3d}  mean±SD={s.mean():.3f}±{s.std():.3f}  median(IQR)={s.median():.2f}({s.quantile(0.25):.2f}–{s.quantile(0.75):.2f})")

    # Kruskal-Wallis (non-parametric, 2+ groups)
    groups = [df.loc[df['Treatment'] == t, 'User Event'].values for t in treatments]
    h_stat, p_value = stats.kruskal(*groups)
    print("\n  Kruskal-Wallis H test:")
    print("    H0: The distributions of User Event per file are the same across all treatments.")
    print(f"    H statistic: {h_stat:.3f}")
    print(f"    p-value:     {p_value:.4f}")

    # --- 2. Events per second (User Event / Duration) by Treatment ---
    df = df.copy()
    df['Events_per_sec'] = df['User Event'] / df['Duration (s)']

    print("\n--- Events per second (User Event / Duration (s), by Treatment) ---")
    for t in treatments:
        s = df.loc[df['Treatment'] == t, 'Events_per_sec']
        print(f"  {t}:")
        print(f"    n={len(s):3d}  mean={s.mean():.6f}  SD={s.std():.6f}")
        print(f"    min={s.min():.6f}  max={s.max():.6f}  median={s.median():.6f}")

    groups_eps = [df.loc[df['Treatment'] == t, 'Events_per_sec'].values for t in treatments]
    h_eps, p_eps = stats.kruskal(*groups_eps)
    print("\n  Kruskal-Wallis H test (Events per second):")
    print("    H0: The distributions of Events per second are the same across all treatments.")
    print(f"    H statistic: {h_eps:.3f}")
    print(f"    p-value:     {p_eps:.4f}")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    run()
    summary()