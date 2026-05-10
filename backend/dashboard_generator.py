"""
Dashboard Generator Module
Creates matplotlib charts for resume analysis results.
Generates: match comparison bar chart, skill cluster pie chart,
industry fit chart, and learning mindmap visualization.
"""
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os
import json

# Output directory for generated charts
CHARTS_DIR = 'charts'
os.makedirs(CHARTS_DIR, exist_ok=True)

# Color palette — premium dark theme
COLORS = {
    'bg': '#0f1117',
    'card_bg': '#1a1d2e',
    'text': '#e2e8f0',
    'text_dim': '#94a3b8',
    'accent_green': '#22c55e',
    'accent_blue': '#3b82f6',
    'accent_purple': '#a855f7',
    'accent_orange': '#f97316',
    'accent_red': '#ef4444',
    'accent_cyan': '#06b6d4',
    'accent_pink': '#ec4899',
    'accent_yellow': '#eab308',
    'grid': '#2a2d3e',
}

PALETTE = ['#3b82f6', '#22c55e', '#a855f7', '#f97316', '#06b6d4',
           '#ec4899', '#eab308', '#ef4444', '#14b8a6', '#8b5cf6',
           '#f43f5e', '#84cc16', '#0ea5e9']


def _apply_dark_theme(fig, ax):
    """Apply consistent dark theme to figure and axes."""
    fig.patch.set_facecolor(COLORS['bg'])
    if isinstance(ax, np.ndarray):
        for a in ax.flat:
            a.set_facecolor(COLORS['card_bg'])
            a.tick_params(colors=COLORS['text'], labelsize=9)
            a.spines['top'].set_visible(False)
            a.spines['right'].set_visible(False)
            a.spines['bottom'].set_color(COLORS['grid'])
            a.spines['left'].set_color(COLORS['grid'])
    else:
        ax.set_facecolor(COLORS['card_bg'])
        ax.tick_params(colors=COLORS['text'], labelsize=9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color(COLORS['grid'])
        ax.spines['left'].set_color(COLORS['grid'])


def generate_role_match_chart(session_id, role_results):
    """
    Bar chart showing match % for each role analyzed.
    Bars colored green (≥70%), orange (50-69%), red (<50%).
    """
    if not role_results:
        return None

    roles = [r['job_role'] if len(r['job_role']) <= 25 else r['job_role'][:22] + '...' for r in role_results]
    scores = [r['match_percentage'] for r in role_results]

    # Color based on threshold
    bar_colors = []
    for s in scores:
        if s >= 70:
            bar_colors.append(COLORS['accent_green'])
        elif s >= 50:
            bar_colors.append(COLORS['accent_orange'])
        else:
            bar_colors.append(COLORS['accent_red'])

    fig, ax = plt.subplots(figsize=(max(10, len(roles) * 1.2), 6))
    _apply_dark_theme(fig, ax)

    bars = ax.barh(roles, scores, color=bar_colors, height=0.6, edgecolor='none')

    # Add score labels on bars
    for bar, score in zip(bars, scores):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f'{score}%', va='center', ha='left',
                color=COLORS['text'], fontsize=10, fontweight='bold')

    # 70% threshold line
    ax.axvline(x=70, color=COLORS['accent_yellow'], linestyle='--', alpha=0.7, linewidth=1.5)
    ax.text(71, len(roles) - 0.5, '70% Apply Threshold', color=COLORS['accent_yellow'],
            fontsize=8, alpha=0.8)

    ax.set_xlim(0, 105)
    ax.set_xlabel('Match Percentage (%)', color=COLORS['text'], fontsize=11)
    ax.set_title('Resume Match Score by Role', color=COLORS['text'], fontsize=14, fontweight='bold', pad=15)
    ax.invert_yaxis()

    # Legend
    legend_patches = [
        mpatches.Patch(color=COLORS['accent_green'], label='≥ 70% — Ready to Apply'),
        mpatches.Patch(color=COLORS['accent_orange'], label='50-69% — Needs Some Skills'),
        mpatches.Patch(color=COLORS['accent_red'], label='< 50% — Significant Gap'),
    ]
    ax.legend(handles=legend_patches, loc='lower right', fontsize=8,
              facecolor=COLORS['card_bg'], edgecolor=COLORS['grid'], labelcolor=COLORS['text'])

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, f'role_match_{session_id}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close(fig)
    return path


def generate_skill_cluster_chart(session_id, skill_clusters):
    """
    Pie chart showing distribution of user's skills across clusters.
    """
    if not skill_clusters:
        return None

    labels = []
    sizes = []
    for cluster_name, data in skill_clusters.items():
        count = data['count'] if isinstance(data, dict) else data
        if count > 0:
            labels.append(cluster_name)
            sizes.append(count)

    if not sizes:
        return None

    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor(COLORS['bg'])

    colors = PALETTE[:len(labels)]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=None, autopct='%1.1f%%', startangle=140,
        colors=colors, pctdistance=0.8,
        wedgeprops=dict(width=0.5, edgecolor=COLORS['bg'], linewidth=2)
    )

    for t in autotexts:
        t.set_color(COLORS['text'])
        t.set_fontsize(9)
        t.set_fontweight('bold')

    # Legend on the right
    ax.legend(wedges, [f'{l} ({s})' for l, s in zip(labels, sizes)],
              loc='center left', bbox_to_anchor=(1, 0.5),
              fontsize=9, facecolor=COLORS['card_bg'],
              edgecolor=COLORS['grid'], labelcolor=COLORS['text'])

    ax.set_title('Your Skill Distribution by Category',
                 color=COLORS['text'], fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, f'skill_clusters_{session_id}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close(fig)
    return path


def generate_industry_fit_chart(session_id, industries):
    """
    Horizontal bar chart showing industry fit scores.
    """
    if not industries:
        return None

    names = [i['industry'] for i in industries[:10]]
    scores = [i['match_score'] for i in industries[:10]]

    fig, ax = plt.subplots(figsize=(10, 6))
    _apply_dark_theme(fig, ax)

    colors = PALETTE[:len(names)]
    bars = ax.barh(names, scores, color=colors, height=0.6)

    for bar, score in zip(bars, scores):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f'{score}%', va='center', ha='left',
                color=COLORS['text'], fontsize=10, fontweight='bold')

    ax.set_xlim(0, max(scores) + 15 if scores else 100)
    ax.set_xlabel('Industry Fit Score (%)', color=COLORS['text'], fontsize=11)
    ax.set_title('Best-Fit Industries for Your Profile',
                 color=COLORS['text'], fontsize=14, fontweight='bold', pad=15)
    ax.invert_yaxis()

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, f'industry_fit_{session_id}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close(fig)
    return path


def generate_learning_mindmap_chart(session_id, learning_path):
    """
    Visual mindmap showing missing skills grouped by cluster,
    with difficulty color coding and course recommendations.
    """
    if not learning_path or not learning_path.get('clusters'):
        return None

    clusters = learning_path['clusters']

    fig, ax = plt.subplots(figsize=(14, max(8, len(clusters) * 2.5)))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])
    ax.set_xlim(-1, 10)

    total_skills = sum(len(c['skills']) for c in clusters)
    ax.set_ylim(-1, total_skills + len(clusters) * 1.5 + 1)
    ax.axis('off')

    # Title
    ax.text(5, total_skills + len(clusters) * 1.5, 'LEARNING ROADMAP',
            ha='center', va='center', fontsize=18, fontweight='bold',
            color=COLORS['accent_cyan'],
            bbox=dict(boxstyle='round,pad=0.5', facecolor=COLORS['card_bg'],
                      edgecolor=COLORS['accent_cyan'], linewidth=2))

    y_pos = total_skills + len(clusters) * 1.5 - 2
    difficulty_colors = {
        'Easy': COLORS['accent_green'],
        'Medium': COLORS['accent_orange'],
        'Hard': COLORS['accent_red'],
        'Unknown': COLORS['text_dim']
    }

    for i, cluster in enumerate(clusters):
        # Cluster header
        ax.text(0.5, y_pos, f"📚 {cluster['cluster']}",
                fontsize=12, fontweight='bold', color=PALETTE[i % len(PALETTE)],
                bbox=dict(boxstyle='round,pad=0.4', facecolor=COLORS['card_bg'],
                          edgecolor=PALETTE[i % len(PALETTE)], linewidth=1.5))

        for skill_info in cluster['skills']:
            y_pos -= 1.2
            diff = skill_info.get('difficulty', 'Unknown')
            color = difficulty_colors.get(diff, COLORS['text_dim'])

            # Connector line
            ax.plot([1.5, 2.5], [y_pos + 0.6, y_pos], color=PALETTE[i % len(PALETTE)],
                    linewidth=1, alpha=0.5)

            # Skill box
            skill_name = skill_info['skill'].title()
            ax.text(2.7, y_pos, f"● {skill_name}", fontsize=10, color=color, fontweight='bold')

            # Difficulty tag
            ax.text(6.5, y_pos, f"[{diff}]", fontsize=8, color=color, fontstyle='italic')

            # Related skills hint
            related = skill_info.get('you_already_know', [])
            if related:
                hint = f"You know: {', '.join(r.title() for r in related[:3])}"
                ax.text(2.7, y_pos - 0.4, hint, fontsize=7, color=COLORS['text_dim'])

        y_pos -= 1.5

    # Legend
    legend_y = 0
    ax.text(7, legend_y + 1.5, 'Difficulty:', fontsize=9, color=COLORS['text'], fontweight='bold')
    for diff, color in difficulty_colors.items():
        if diff != 'Unknown':
            ax.text(7, legend_y, f"● {diff}", fontsize=9, color=color)
            legend_y -= 0.8

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, f'learning_mindmap_{session_id}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close(fig)
    return path


def generate_full_dashboard(session_id, role_results, skill_clusters, industries, learning_path):
    """
    Generate a combined 2x2 dashboard with all charts.
    Returns the path to the saved dashboard image.
    """
    fig, axes = plt.subplots(2, 2, figsize=(20, 14))
    fig.patch.set_facecolor(COLORS['bg'])
    fig.suptitle('RESUME SKILL GAP ANALYSIS — DASHBOARD',
                 fontsize=20, fontweight='bold', color=COLORS['accent_cyan'], y=0.98)

    # --- Chart 1: Role Match Bars (top-left) ---
    ax1 = axes[0, 0]
    ax1.set_facecolor(COLORS['card_bg'])
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['bottom'].set_color(COLORS['grid'])
    ax1.spines['left'].set_color(COLORS['grid'])
    ax1.tick_params(colors=COLORS['text'], labelsize=8)

    if role_results:
        roles = [r['job_role'][:20] for r in role_results[:8]]
        scores = [r['match_percentage'] for r in role_results[:8]]
        bar_colors = [COLORS['accent_green'] if s >= 70 else COLORS['accent_orange'] if s >= 50 else COLORS['accent_red'] for s in scores]
        bars = ax1.barh(roles, scores, color=bar_colors, height=0.6)
        for bar, score in zip(bars, scores):
            ax1.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                     f'{score}%', va='center', fontsize=8, color=COLORS['text'])
        ax1.axvline(x=70, color=COLORS['accent_yellow'], linestyle='--', alpha=0.5)
        ax1.set_xlim(0, 105)
        ax1.invert_yaxis()
    ax1.set_title('Match Score by Role', color=COLORS['text'], fontsize=12, fontweight='bold')

    # --- Chart 2: Skill Cluster Pie (top-right) ---
    ax2 = axes[0, 1]
    ax2.set_facecolor(COLORS['bg'])

    if skill_clusters:
        labels = []
        sizes = []
        for name, data in skill_clusters.items():
            count = data['count'] if isinstance(data, dict) else data
            if count > 0:
                labels.append(name[:18])
                sizes.append(count)
        if sizes:
            colors = PALETTE[:len(labels)]
            wedges, _, autotexts = ax2.pie(sizes, labels=None, autopct='%1.0f%%',
                                            startangle=140, colors=colors, pctdistance=0.8,
                                            wedgeprops=dict(width=0.5, edgecolor=COLORS['bg']))
            for t in autotexts:
                t.set_color(COLORS['text'])
                t.set_fontsize(7)
            ax2.legend(wedges, labels, loc='center left', bbox_to_anchor=(1, 0.5),
                       fontsize=7, facecolor=COLORS['card_bg'],
                       edgecolor=COLORS['grid'], labelcolor=COLORS['text'])
    ax2.set_title('Skill Distribution', color=COLORS['text'], fontsize=12, fontweight='bold')

    # --- Chart 3: Industry Fit (bottom-left) ---
    ax3 = axes[1, 0]
    ax3.set_facecolor(COLORS['card_bg'])
    ax3.spines['top'].set_visible(False)
    ax3.spines['right'].set_visible(False)
    ax3.spines['bottom'].set_color(COLORS['grid'])
    ax3.spines['left'].set_color(COLORS['grid'])
    ax3.tick_params(colors=COLORS['text'], labelsize=8)

    if industries:
        ind_names = [i['industry'][:18] for i in industries[:8]]
        ind_scores = [i['match_score'] for i in industries[:8]]
        colors = PALETTE[:len(ind_names)]
        bars = ax3.barh(ind_names, ind_scores, color=colors, height=0.6)
        for bar, score in zip(bars, ind_scores):
            ax3.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                     f'{score}%', va='center', fontsize=8, color=COLORS['text'])
        ax3.set_xlim(0, max(ind_scores) + 15 if ind_scores else 100)
        ax3.invert_yaxis()
    ax3.set_title('Industry Fit Score', color=COLORS['text'], fontsize=12, fontweight='bold')

    # --- Chart 4: Missing Skills Summary (bottom-right) ---
    ax4 = axes[1, 1]
    ax4.set_facecolor(COLORS['card_bg'])
    ax4.axis('off')
    ax4.set_title('Top Skills to Learn', color=COLORS['text'], fontsize=12, fontweight='bold')

    if learning_path and learning_path.get('clusters'):
        y = 0.95
        for cluster in learning_path['clusters'][:5]:
            ax4.text(0.05, y, f"▸ {cluster['cluster']}", fontsize=10,
                     color=COLORS['accent_cyan'], fontweight='bold',
                     transform=ax4.transAxes)
            y -= 0.06
            for skill_info in cluster['skills'][:3]:
                diff = skill_info.get('difficulty', '?')
                dcolor = COLORS['accent_green'] if diff == 'Easy' else COLORS['accent_orange'] if diff == 'Medium' else COLORS['accent_red']
                ax4.text(0.1, y, f"• {skill_info['skill'].title()} [{diff}]",
                         fontsize=8, color=dcolor, transform=ax4.transAxes)
                y -= 0.05
            y -= 0.03

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    path = os.path.join(CHARTS_DIR, f'full_dashboard_{session_id}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close(fig)
    return path
