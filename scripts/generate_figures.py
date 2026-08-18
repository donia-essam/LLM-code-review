from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = ROOT / "artifacts" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

import matplotlib.pyplot as plt
import numpy as np

# Set clean aesthetic style
plt.rcParams.update({
    'font.size': 11,
    'font.family': 'sans-serif',
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.titlesize': 14,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight'
})

# ----------------------------------------------------
# Figure 1: End-to-End System Performance Comparison
# ----------------------------------------------------
def generate_fig1_system_comparison():
    systems = ['Baseline A\n(Unverified LLM)', 'Baseline B\n(LLM Judge Proxy)', 'Proposed\n(Grounded Verifier)']
    metrics = ['Precision', 'Recall', 'F1 Score', 'Hallucination Rate']
    
    # Values from empirical evaluation
    values = np.array([
        [0.143, 0.086, 0.107, 0.858],  # Baseline A
        [0.143, 0.086, 0.107, 0.858],  # Baseline B
        [1.000, 0.028, 0.055, 0.000]   # Proposed
    ])
    
    x = np.arange(len(metrics))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(9, 5.5))
    
    colors = ['#5b84b1', '#fc766a', '#2e8b57']
    
    for i in range(len(systems)):
        bars = ax.bar(x + (i - 1) * width, values[i], width, label=systems[i], color=colors[i], edgecolor='black', alpha=0.85)
        for bar in bars:
            height = bar.get_height()
            if height > 0.01:
                ax.annotate(f'{height:.3f}',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=9, fontweight='bold')
            else:
                ax.annotate('0.000',
                            xy=(bar.get_x() + bar.get_width() / 2, 0.01),
                            xytext=(0, 3),
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_ylabel('Score / Rate (0.0 to 1.0)')
    ax.set_title('Figure 1: End-to-End Code Review System Performance (RQ2)')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontweight='bold')
    ax.set_ylim(0, 1.15)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    ax.legend(frameon=True, facecolor='white', loc='upper right')
    
    out_path = FIGURES_DIR / "fig1_system_comparison.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Generated {out_path}")


# ----------------------------------------------------
# Figure 2: RQ3 Breakdown by Bug Class
# ----------------------------------------------------
def generate_fig2_bug_class_breakdown():
    bug_classes = ['Unused Variables', 'Null Safety Violations', 'Off-by-One Bounds']
    
    raw_comments = [646, 41, 43]
    tps = [36, 34, 34]
    fps = [610, 7, 9]
    grounding_acc = [94.44, 0.0, 0.0]
    hallu_caught = [100.0, 100.0, 100.0]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    
    # Subplot 1: Reviewer Emission & Ground Truth
    x = np.arange(len(bug_classes))
    width = 0.35
    ax1.bar(x - width/2, tps, width, label='True Injected Bugs (TP)', color='#2e8b57', edgecolor='black', alpha=0.85)
    ax1.bar(x + width/2, fps, width, label='Hallucinations (FP)', color='#d9534f', edgecolor='black', alpha=0.85)
    
    for i, (tp_val, fp_val) in enumerate(zip(tps, fps)):
        ax1.annotate(str(tp_val), (i - width/2, tp_val + 10), ha='center', fontsize=9, fontweight='bold')
        ax1.annotate(str(fp_val), (i + width/2, fp_val + 10), ha='center', fontsize=9, fontweight='bold')
        
    ax1.set_title('Review Agent Claims by Bug Class')
    ax1.set_xticks(x)
    ax1.set_xticklabels(bug_classes, fontsize=9)
    ax1.set_ylabel('Number of Claims')
    ax1.set_ylim(0, 700)
    ax1.grid(axis='y', linestyle='--', alpha=0.4)
    ax1.legend()
    
    # Subplot 2: Verifier Grounding Accuracy & Hallucination Rejection
    ax2.bar(x - width/2, grounding_acc, width, label='TP Grounding Accuracy (%)', color='#337ab7', edgecolor='black', alpha=0.85)
    ax2.bar(x + width/2, hallu_caught, width, label='Hallucination Catch Rate (%)', color='#5cb85c', edgecolor='black', alpha=0.85)
    
    for i, (ga, hc) in enumerate(zip(grounding_acc, hallu_caught)):
        ax2.annotate(f"{ga:.1f}%", (i - width/2, ga + 2), ha='center', fontsize=9, fontweight='bold')
        ax2.annotate(f"{hc:.1f}%", (i + width/2, hc + 2), ha='center', fontsize=9, fontweight='bold')
        
    ax2.set_title('Static Verifier Performance by Bug Class (RQ3)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(bug_classes, fontsize=9)
    ax2.set_ylabel('Percentage (%)')
    ax2.set_ylim(0, 115)
    ax2.grid(axis='y', linestyle='--', alpha=0.4)
    ax2.legend(loc='lower right')
    
    plt.tight_layout()
    out_path = FIGURES_DIR / "fig2_rq3_bug_class_breakdown.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Generated {out_path}")


# ----------------------------------------------------
# Figure 3: Precision vs Hallucination Suppression
# ----------------------------------------------------
def generate_fig3_tradeoff():
    fig, ax = plt.subplots(figsize=(8, 5))
    
    systems = ['Baseline A\n(Unfiltered)', 'Baseline B\n(Proxy Filtered)', 'Proposed\n(Grounded Verifier)']
    precisions = [14.25, 14.25, 100.0]
    hallu_rates = [85.75, 85.75, 0.0]
    
    x = np.arange(len(systems))
    width = 0.35
    
    ax.bar(x - width/2, precisions, width, label='Precision (%)', color='#2b580c', edgecolor='black', alpha=0.85)
    ax.bar(x + width/2, hallu_rates, width, label='Hallucination Rate (%)', color='#b83b5e', edgecolor='black', alpha=0.85)
    
    for i, (p, h) in enumerate(zip(precisions, hallu_rates)):
        ax.annotate(f"{p:.1f}%", (i - width/2, p + 2), ha='center', fontsize=10, fontweight='bold')
        ax.annotate(f"{h:.1f}%", (i + width/2, h + 2), ha='center', fontsize=10, fontweight='bold')
        
    ax.set_ylabel('Percentage (%)')
    ax.set_title('Figure 3: Precision vs. Hallucination Suppression Impact')
    ax.set_xticks(x)
    ax.set_xticklabels(systems)
    ax.set_ylim(0, 115)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    ax.legend(frameon=True, loc='center right')
    
    out_path = FIGURES_DIR / "fig3_tradeoff_curve.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Generated {out_path}")


# ----------------------------------------------------
# Figure 4: McNemar 2x2 Contingency Matrix Heatmap
# ----------------------------------------------------
def generate_fig4_mcnemar_heatmap():
    matrix = np.array([
        [34, 70],    # Baseline B Correct (Proposed Correct, Proposed Incorrect)
        [626, 0]     # Baseline B Incorrect (Proposed Correct, Proposed Incorrect)
    ])
    
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    cax = ax.matshow(matrix, cmap='Blues', alpha=0.8)
    
    for (i, j), z in np.ndenumerate(matrix):
        label_txt = f"{z}\n"
        if (i, j) == (0, 0):
            label_txt += "(Both Correct)"
        elif (i, j) == (0, 1):
            label_txt += "(Baseline B Only)"
        elif (i, j) == (1, 0):
            label_txt += "(Proposed Only)"
        elif (i, j) == (1, 1):
            label_txt += "(Both Incorrect)"
            
        color = 'white' if z > 300 else 'black'
        ax.text(j, i, label_txt, ha='center', va='center', fontsize=11, fontweight='bold', color=color)
        
    fig.colorbar(cax)
    
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(['Proposed Correct', 'Proposed Incorrect'], fontsize=11)
    ax.set_yticklabels(['Baseline B\nCorrect', 'Baseline B\nIncorrect'], fontsize=11)
    
    ax.set_xlabel('Proposed Grounded Verifier Outcome', fontsize=12, labelpad=10)
    ax.set_ylabel('Baseline B Proxy Judge Outcome', fontsize=12, labelpad=10)
    ax.set_title('Figure 4: McNemar 2x2 Paired Matrix (p < 0.001)', pad=20, fontsize=13, fontweight='bold')
    
    out_path = FIGURES_DIR / "fig4_mcnemar_contingency.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Generated {out_path}")


if __name__ == "__main__":
    generate_fig1_system_comparison()
    generate_fig2_bug_class_breakdown()
    generate_fig3_tradeoff()
    generate_fig4_mcnemar_heatmap()
    print("All figures successfully generated in artifacts/figures/")
