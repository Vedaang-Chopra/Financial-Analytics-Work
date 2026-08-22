#!/usr/bin/env python3
"""
Comprehensive Data Exploration & Visualization Script
=======================================================

Purpose: Complete end-to-end exploration of the Mutual Fund Ingestion Pipeline data.
This script connects to the PostgreSQL database, inspects all 17 tables, analyzes
provider profiles, source registry, and generates interactive Plotly visualizations.

Prerequisites: 
- DATABASE_URL environment variable set (PostgreSQL)
- Or run with SQLite for local inspection (uses temp DB)

Outputs: Interactive charts (saved as HTML), summary tables, data quality reports
"""

import sys
import os
import json
import logging
import tempfile
from pathlib import Path
from collections import Counter
from datetime import datetime

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker

# Visualization
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

# Configure Plotly
pio.renderers.default = 'browser'

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(name)s: %(message)s'
)
logger = logging.getLogger('data_exploration')


def find_repo_root():
    """Find the repository root by looking for AGENTS.md"""
    root = Path('.').resolve()
    while not (root / 'AGENTS.md').exists() and root != root.parent:
        root = root.parent
    return root


ROOT = find_repo_root()
sys.path.insert(0, str(ROOT))

# Import project modules
from mutual_fund_ingestion.agent.db import create_tables, get_session_maker
from mutual_fund_ingestion.agent.config import AgentConfig

from db_config import generic_database_url


def setup_database():
    """Setup database connection - uses PostgreSQL if available, otherwise SQLite"""
    DATABASE_URL = generic_database_url()

    USE_SQLITE_DEMO = not DATABASE_URL.startswith(("postgresql://", "postgres://"))

    if USE_SQLITE_DEMO:
        print('[MODE] Using SQLite demo database (no PostgreSQL connection)')
        tmp_dir = tempfile.mkdtemp(prefix='mf_exploration_')
        db_path = Path(tmp_dir) / 'exploration.db'
        DATABASE_URL = f'sqlite:///{db_path}'
        create_tables(DATABASE_URL)
        print(f'[DB] Created SQLite at: {db_path}')
    else:
        print(f'[MODE] Using PostgreSQL: {DATABASE_URL.split("@")[1] if "@" in DATABASE_URL else DATABASE_URL}')
    
    engine = create_engine(DATABASE_URL)
    Session = get_session_maker(DATABASE_URL)
    
    # Verify connection
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1 as test')).fetchone()
        print(f'[DB] Connection verified: {result}')
    
    return engine, Session, DATABASE_URL


def inspect_schema(engine):
    """Inspect all tables in the database"""
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    
    print(f'\nTotal tables in database: {len(tables)}')
    print('=' * 60)
    
    table_info = []
    for table_name in sorted(tables):
        columns = inspector.get_columns(table_name)
        indexes = inspector.get_indexes(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        
        with engine.connect() as conn:
            try:
                count = conn.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()
            except Exception as e:
                count = f'ERROR: {e}'
        
        table_info.append({
            'table_name': table_name,
            'columns': len(columns),
            'indexes': len(indexes),
            'foreign_keys': len(foreign_keys),
            'row_count': count
        })
        
        print(f'\n📋 {table_name}')
        print(f'   Columns: {len(columns)} | Indexes: {len(indexes)} | FKs: {len(foreign_keys)} | Rows: {count}')
        for col in columns:
            nullable = 'NULL' if col['nullable'] else 'NOT NULL'
            default = f" DEFAULT {col['default']}" if col['default'] is not None else ''
            print(f'   - {col["name"]}: {col["type"]} {nullable}{default}')
    
    return pd.DataFrame(table_info), tables, inspector


def create_schema_visualization(df_tables, output_dir):
    """Create interactive table schema visualization"""
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=['Table Name', 'Columns', 'Indexes', 'Foreign Keys', 'Row Count'],
            fill_color='#1f77b4',
            font=dict(color='white', size=12),
            align='left'
        ),
        cells=dict(
            values=[
                df_tables['table_name'],
                df_tables['columns'],
                df_tables['indexes'],
                df_tables['foreign_keys'],
                df_tables['row_count']
            ],
            fill_color='#f8f9fa',
            font=dict(color='black', size=11),
            align='left',
            height=30
        )
    )])
    
    fig.update_layout(
        title=f'Database Schema Overview - All {len(df_tables)} Tables',
        height=600,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    output_path = output_dir / 'schema_overview.html'
    fig.write_html(str(output_path))
    print(f'Saved schema visualization to {output_path}')
    return fig


def create_erd_visualization(inspector, tables, output_dir):
    """Create ERD visualization from foreign keys"""
    relationships = []
    for table_name in sorted(tables):
        foreign_keys = inspector.get_foreign_keys(table_name)
        for fk in foreign_keys:
            relationships.append({
                'from_table': table_name,
                'from_column': ', '.join(fk['constrained_columns']),
                'to_table': fk['referred_table'],
                'to_column': ', '.join(fk['referred_columns'])
            })
    
    df_relationships = pd.DataFrame(relationships)
    
    print('\nENTITY RELATIONSHIP MAP')
    print('=' * 80)
    if not df_relationships.empty:
        for _, rel in df_relationships.iterrows():
            print(f'{rel["from_table"]}.{rel["from_column"]} ────► {rel["to_table"]}.{rel["to_column"]}')
    else:
        print('No foreign key relationships found')
    
    if not df_relationships.empty:
        all_tables = list(set(df_relationships['from_table'].tolist() + df_relationships['to_table'].tolist()))
        table_to_idx = {t: i for i, t in enumerate(all_tables)}
        
        source = [table_to_idx[row['from_table']] for _, row in df_relationships.iterrows()]
        target = [table_to_idx[row['to_table']] for _, row in df_relationships.iterrows()]
        value = [1] * len(df_relationships)
        
        fig_sankey = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color='black', width=0.5),
                label=all_tables,
                color='#1f77b4'
            ),
            link=dict(
                source=source,
                target=target,
                value=value,
                color='rgba(31, 119, 180, 0.3)'
            )
        )])
        
        fig_sankey.update_layout(
            title='Table Relationships (Foreign Keys)',
            font_size=10,
            height=600
        )
        
        output_path = output_dir / 'erd_sankey.html'
        fig_sankey.write_html(str(output_path))
        print(f'Saved ERD visualization to {output_path}')
        return fig_sankey
    
    return None


def analyze_pipeline_tables(engine, inspector, tables, output_dir):
    """Deep dive into pipeline and canonical tables"""
    pipeline_tables = [
        'ingestion_runs', 'source_pages', 'discovered_links', 'dataset_candidates',
        'raw_artifacts', 'staging_rows', 'validation_results', 'quarantine_rows', 'retry_queue'
    ]
    
    canonical_tables = [
        'amcs', 'schemes', 'nav_history', 'documents', 'instruments',
        'portfolio_snapshots', 'portfolio_holdings'
    ]
    
    print('\nPIPELINE TABLES DETAIL')
    print('=' * 80)
    
    table_data = {}
    
    for table_name in pipeline_tables + canonical_tables:
        if table_name not in tables:
            continue
            
        columns = inspector.get_columns(table_name)
        with engine.connect() as conn:
            try:
                count = conn.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()
                if count > 0 and count < 10000:
                    sample = conn.execute(text(f'SELECT * FROM {table_name} LIMIT 3')).mappings().all()
                else:
                    sample = []
            except Exception as e:
                count = f'ERROR: {e}'
                sample = []
        
        print(f'\n📊 {table_name} ({count} rows)')
        print(f'   Columns: {", ".join([c["name"] for c in columns])}')
        
        if sample:
            print('   Sample rows:')
            for row in sample:
                row_str = ', '.join([f'{k}={str(v)[:50]}' for k, v in row.items()])
                print(f'     {row_str}')
        
        # Load full data for key tables
        if table_name in ['ingestion_runs', 'source_pages', 'discovered_links', 'dataset_candidates',
                          'raw_artifacts', 'validation_results', 'quarantine_rows', 'retry_queue',
                          'amcs', 'schemes', 'nav_history', 'portfolio_snapshots', 'portfolio_holdings']:
            with engine.connect() as conn:
                try:
                    df = pd.read_sql(text(f'SELECT * FROM {table_name}'), conn)
                    table_data[table_name] = df
                except Exception as e:
                    print(f'   Failed to load: {e}')
    
    return table_data


def analyze_ingestion_runs(runs_df, output_dir):
    """Analyze ingestion runs timeline and status"""
    if runs_df.empty:
        print('No ingestion runs found in database')
        return
    
    print(f'\nTotal ingestion runs: {len(runs_df)}')
    
    # Status distribution
    status_counts = runs_df['status'].value_counts()
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Run Status Distribution', 'Pages vs Files per Run'),
        specs=[[{'type': 'pie'}, {'type': 'scatter'}]]
    )
    
    fig.add_trace(
        go.Pie(labels=status_counts.index, values=status_counts.values, name='Status', textinfo='label+percent+value'),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=runs_df['pages_seen'], y=runs_df['files_seen'],
            mode='markers+text',
            text=runs_df['id'].astype(str).str[:8],
            textposition='top center',
            marker=dict(size=12, color=runs_df['rows_inserted'], colorscale='Viridis', showscale=True,
                       colorbar=dict(title='Rows Inserted')),
            name='Runs'
        ),
        row=1, col=2
    )
    
    fig.update_layout(height=500, title_text='Ingestion Runs Analysis')
    output_path = output_dir / 'ingestion_runs_analysis.html'
    fig.write_html(str(output_path))
    print(f'Saved ingestion runs analysis to {output_path}')
    return fig


def analyze_source_pages(source_pages_df, output_dir):
    """Analyze source pages"""
    if source_pages_df.empty:
        print('No source pages found')
        return
    
    print(f'\nTotal source pages: {len(source_pages_df)}')
    
    domain_counts = source_pages_df['domain'].value_counts().head(20)
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Top 20 Domains by Page Count',
            'Status Code Distribution',
            'Content Type Distribution',
            'Page Relevance Distribution'
        ),
        specs=[[{'type': 'bar'}, {'type': 'pie'}],
               [{'type': 'pie'}, {'type': 'pie'}]]
    )
    
    fig.add_trace(go.Bar(x=domain_counts.values, y=domain_counts.index, orientation='h', marker_color='#1f77b4', name='Pages'), row=1, col=1)
    
    status_counts = source_pages_df['status_code'].value_counts()
    fig.add_trace(go.Pie(labels=[str(s) for s in status_counts.index], values=status_counts.values, name='Status Codes'), row=1, col=2)
    
    content_counts = source_pages_df['content_type'].value_counts().head(10)
    fig.add_trace(go.Pie(labels=content_counts.index, values=content_counts.values, name='Content Types'), row=2, col=1)
    
    relevance_counts = source_pages_df['page_relevance'].value_counts()
    fig.add_trace(go.Pie(labels=relevance_counts.index, values=relevance_counts.values, name='Relevance'), row=2, col=2)
    
    fig.update_layout(height=800, showlegend=False, title_text='Source Pages Analysis')
    output_path = output_dir / 'source_pages_analysis.html'
    fig.write_html(str(output_path))
    print(f'Saved source pages analysis to {output_path}')
    return fig


def analyze_discovered_links(links_df, candidates_df, output_dir):
    """Analyze discovered links and dataset candidates"""
    print(f'\nDiscovered links: {len(links_df)}')
    print(f'Dataset candidates: {len(candidates_df)}')
    
    if not links_df.empty:
        link_type_counts = links_df['link_type'].value_counts()
        dataset_hint_counts = links_df['dataset_type_hint'].value_counts()
        file_type_counts = links_df['file_type_hint'].value_counts()
        follow_counts = links_df['should_follow'].value_counts()
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Link Type Distribution',
                'Dataset Type Hint Distribution',
                'File Type Hint Distribution',
                'Should Follow Distribution'
            ),
            specs=[[{'type': 'pie'}, {'type': 'pie'}],
                   [{'type': 'pie'}, {'type': 'pie'}]]
        )
        
        fig.add_trace(go.Pie(labels=link_type_counts.index, values=link_type_counts.values, name='Link Types'), row=1, col=1)
        fig.add_trace(go.Pie(labels=dataset_hint_counts.index, values=dataset_hint_counts.values, name='Dataset Hints'), row=1, col=2)
        fig.add_trace(go.Pie(labels=file_type_counts.index, values=file_type_counts.values, name='File Types'), row=2, col=1)
        fig.add_trace(go.Pie(labels=[str(f) for f in follow_counts.index], values=follow_counts.values, name='Follow'), row=2, col=2)
        
        fig.update_layout(height=700, showlegend=False, title_text='Discovered Links Analysis')
        output_path = output_dir / 'discovered_links_analysis.html'
        fig.write_html(str(output_path))
        print(f'Saved discovered links analysis to {output_path}')
    
    if not candidates_df.empty:
        print('\nDataset Candidates Detail:')
        print(candidates_df[['url', 'dataset_type', 'provider_hint', 'file_type', 'confidence', 'status']].to_string(index=False))
        
        dataset_type_counts = candidates_df['dataset_type'].value_counts()
        provider_counts = candidates_df['provider_hint'].value_counts().head(15)
        file_type_cand = candidates_df['file_type'].value_counts()
        confidence_dist = candidates_df['confidence'].dropna()
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Dataset Type Distribution',
                'Top 15 Providers by Candidates',
                'File Type Distribution',
                'Confidence Score Distribution'
            ),
            specs=[[{'type': 'bar'}, {'type': 'bar'}],
                   [{'type': 'pie'}, {'type': 'histogram'}]]
        )
        
        fig.add_trace(go.Bar(x=dataset_type_counts.index, y=dataset_type_counts.values, marker_color='#2ca02c', name='Types'), row=1, col=1)
        fig.add_trace(go.Bar(x=provider_counts.values, y=provider_counts.index, orientation='h', marker_color='#ff7f0e', name='Providers'), row=1, col=2)
        fig.add_trace(go.Pie(labels=file_type_cand.index, values=file_type_cand.values, name='File Types'), row=2, col=1)
        fig.add_trace(go.Histogram(x=confidence_dist, nbinsx=20, marker_color='#d62728', name='Confidence'), row=2, col=2)
        
        fig.update_layout(height=800, showlegend=False, title_text='Dataset Candidates Analysis')
        output_path = output_dir / 'dataset_candidates_analysis.html'
        fig.write_html(str(output_path))
        print(f'Saved dataset candidates analysis to {output_path}')
    
    return None


def analyze_raw_artifacts(artifacts_df, output_dir):
    """Analyze raw artifacts and downloads"""
    if artifacts_df.empty:
        print('No raw artifacts found')
        return
    
    print(f'\nTotal raw artifacts: {len(artifacts_df)}')
    print(f'Retained: {artifacts_df["retained"].sum()} / {len(artifacts_df)}')
    
    artifact_type_counts = artifacts_df['artifact_type'].value_counts()
    file_type_counts = artifacts_df['file_type'].value_counts()
    content_type_counts = artifacts_df['content_type'].value_counts().head(15)
    
    size_df = artifacts_df.dropna(subset=['size_bytes'])
    if not size_df.empty:
        size_df['size_mb'] = size_df['size_bytes'] / (1024 * 1024)
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Artifact Type Distribution',
            'File Type Distribution',
            'Content Type Distribution (Top 15)',
            'File Size Distribution (MB)'
        ),
        specs=[[{'type': 'pie'}, {'type': 'pie'}],
               [{'type': 'bar'}, {'type': 'histogram'}]]
    )
    
    fig.add_trace(go.Pie(labels=artifact_type_counts.index, values=artifact_type_counts.values, name='Artifact Types'), row=1, col=1)
    fig.add_trace(go.Pie(labels=file_type_counts.index, values=file_type_counts.values, name='File Types'), row=1, col=2)
    fig.add_trace(go.Bar(x=content_type_counts.values, y=content_type_counts.index, orientation='h', marker_color='#9467bd', name='Content Types'), row=2, col=1)
    
    if not size_df.empty:
        fig.add_trace(go.Histogram(x=size_df['size_mb'], nbinsx=30, marker_color='#8c564b', name='Size (MB)'), row=2, col=2)
    
    fig.update_layout(height=800, showlegend=False, title_text='Raw Artifacts Analysis')
    output_path = output_dir / 'raw_artifacts_analysis.html'
    fig.write_html(str(output_path))
    print(f'Saved raw artifacts analysis to {output_path}')
    
    # Retention analysis
    retained_by_type = artifacts_df.groupby('file_type')['retained'].agg(['sum', 'count']).reset_index()
    retained_by_type.columns = ['file_type', 'retained', 'total']
    retained_by_type['retention_rate'] = retained_by_type['retained'] / retained_by_type['total'] * 100
    
    fig_ret = px.bar(
        retained_by_type, x='file_type', y='retention_rate',
        title='Retention Rate by File Type (%)', text='retention_rate'
    )
    fig_ret.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    output_path = output_dir / 'retention_rate.html'
    fig_ret.write_html(str(output_path))
    print(f'Saved retention rate analysis to {output_path}')
    
    return fig


def analyze_canonical_data(amcs_df, schemes_df, nav_df, snapshots_df, holdings_df, output_dir):
    """Analyze canonical data tables"""
    print(f'\nAMCs: {len(amcs_df)}')
    print(f'Schemes: {len(schemes_df)}')
    print(f'NAV History records: {len(nav_df)}')
    print(f'Portfolio Snapshots: {len(snapshots_df)}')
    print(f'Portfolio Holdings: {len(holdings_df)}')
    
    figures = []
    
    # AMC visualization
    if not amcs_df.empty:
        fig = px.bar(amcs_df, x='name', title='Registered AMCs', color_discrete_sequence=['#1f77b4'])
        fig.update_layout(xaxis_tickangle=-45, height=400)
        output_path = output_dir / 'amcs.html'
        fig.write_html(str(output_path))
        figures.append(fig)
        print(f'Saved AMCs chart to {output_path}')
    
    # Scheme category distribution
    if not schemes_df.empty and 'category' in schemes_df.columns:
        cat_counts = schemes_df['category'].value_counts()
        fig = px.pie(values=cat_counts.values, names=cat_counts.index, title='Scheme Category Distribution')
        output_path = output_dir / 'scheme_categories.html'
        fig.write_html(str(output_path))
        figures.append(fig)
        print(f'Saved scheme categories to {output_path}')
        
        # Schemes per AMC
        schemes_per_amc = schemes_df.groupby('amc_id').size().reset_index(name='count')
        schemes_per_amc = schemes_per_amc.merge(amcs_df[['id', 'name']], left_on='amc_id', right_on='id', how='left')
        
        fig = px.bar(
            schemes_per_amc.sort_values('count', ascending=True),
            x='count', y='name', orientation='h',
            title='Number of Schemes per AMC', color_discrete_sequence=['#2ca02c']
        )
        output_path = output_dir / 'schemes_per_amc.html'
        fig.write_html(str(output_path))
        figures.append(fig)
        print(f'Saved schemes per AMC to {output_path}')
    
    # NAV History analysis
    if not nav_df.empty:
        nav_df['nav_date'] = pd.to_datetime(nav_df['nav_date'])
        nav_df['nav_value'] = pd.to_numeric(nav_df['nav_value'], errors='coerce')
        
        scheme_nav_counts = nav_df['scheme_code'].value_counts().head(10)
        top_schemes = scheme_nav_counts.index.tolist()
        
        fig = go.Figure()
        for scheme in top_schemes[:5]:
            scheme_data = nav_df[nav_df['scheme_code'] == scheme].sort_values('nav_date')
            fig.add_trace(go.Scatter(
                x=scheme_data['nav_date'], y=scheme_data['nav_value'],
                mode='lines', name=scheme, line=dict(width=1)
            ))
        
        fig.update_layout(title='NAV Trends - Top 5 Schemes by Record Count',
                         xaxis_title='Date', yaxis_title='NAV Value', height=500, hovermode='x unified')
        output_path = output_dir / 'nav_trends.html'
        fig.write_html(str(output_path))
        figures.append(fig)
        print(f'Saved NAV trends to {output_path}')
        
        fig_hist = px.histogram(nav_df.dropna(subset=['nav_value']), x='nav_value', nbins=50, title='NAV Value Distribution')
        output_path = output_dir / 'nav_distribution.html'
        fig_hist.write_html(str(output_path))
        figures.append(fig_hist)
        print(f'Saved NAV distribution to {output_path}')
    
    # Portfolio holdings analysis
    if not holdings_df.empty:
        if 'sector' in holdings_df.columns:
            sector_counts = holdings_df['sector'].value_counts().head(15)
            fig = px.bar(x=sector_counts.values, y=sector_counts.index, orientation='h',
                        title='Top 15 Sectors in Portfolio Holdings', color_discrete_sequence=['#e377c2'])
            output_path = output_dir / 'holdings_sectors.html'
            fig.write_html(str(output_path))
            figures.append(fig)
            print(f'Saved holdings sectors to {output_path}')
        
        if 'asset_class' in holdings_df.columns:
            asset_counts = holdings_df['asset_class'].value_counts()
            fig = px.pie(values=asset_counts.values, names=asset_counts.index, title='Asset Class Distribution in Holdings')
            output_path = output_dir / 'holdings_asset_class.html'
            fig.write_html(str(output_path))
            figures.append(fig)
            print(f'Saved holdings asset class to {output_path}')
        
        if 'market_value' in holdings_df.columns:
            holdings_df['market_value'] = pd.to_numeric(holdings_df['market_value'], errors='coerce')
            mv_df = holdings_df.dropna(subset=['market_value'])
            if not mv_df.empty:
                fig = px.histogram(mv_df, x='market_value', nbins=50, title='Market Value Distribution (INR)', log_y=True)
                output_path = output_dir / 'holdings_market_value.html'
                fig.write_html(str(output_path))
                figures.append(fig)
                print(f'Saved holdings market value to {output_path}')
    
    return figures


def analyze_validation_quarantine(validation_df, quarantine_df, retry_df, output_dir):
    """Analyze validation and quarantine data"""
    print(f'\nValidation results: {len(validation_df)}')
    print(f'Quarantine rows: {len(quarantine_df)}')
    print(f'Retry queue items: {len(retry_df)}')
    
    if not validation_df.empty:
        val_status = validation_df.groupby(['severity', 'status']).size().reset_index(name='count')
        
        fig = px.bar(val_status, x='severity', y='count', color='status',
                    title='Validation Results by Severity and Status', barmode='stack',
                    color_discrete_map={'passed': '#2ca02c', 'failed': '#d62728', 'warning': '#ff7f0e'})
        output_path = output_dir / 'validation_by_severity.html'
        fig.write_html(str(output_path))
        print(f'Saved validation analysis to {output_path}')
        
        failed_checks = validation_df[validation_df['status'] == 'failed']['check_name'].value_counts().head(15)
        failed_checks_df = pd.DataFrame({'check_name': failed_checks.index, 'count': failed_checks.values})
        fig = px.bar(failed_checks_df, x='count', y='check_name', orientation='h',
                    title='Top 15 Failed Validation Checks', color_discrete_sequence=['#d62728'],
                    labels={'count': 'Count', 'check_name': 'Check Name'})
        output_path = output_dir / 'failed_checks.html'
        fig.write_html(str(output_path))
        print(f'Saved failed checks to {output_path}')
    
    if not quarantine_df.empty:
        reason_counts = quarantine_df['reason'].value_counts().head(20)
        reason_df = pd.DataFrame({'reason': reason_counts.index, 'count': reason_counts.values})
        fig = px.bar(reason_df, x='count', y='reason', orientation='h',
                    title='Top 20 Quarantine Reasons', color_discrete_sequence=['#8c564b'],
                    labels={'count': 'Count', 'reason': 'Reason'})
        fig.update_layout(height=600)
        output_path = output_dir / 'quarantine_reasons.html'
        fig.write_html(str(output_path))
        print(f'Saved quarantine reasons to {output_path}')
        
        if 'dataset_type' in quarantine_df.columns:
            q_dt_counts = quarantine_df['dataset_type'].value_counts()
            fig = px.pie(values=q_dt_counts.values, names=q_dt_counts.index, title='Quarantine by Dataset Type')
            output_path = output_dir / 'quarantine_by_type.html'
            fig.write_html(str(output_path))
            print(f'Saved quarantine by type to {output_path}')
    
    return None


def analyze_provider_profiles(output_dir):
    """Analyze provider profiles from JSON artifacts"""
    provider_profiles_path = ROOT / 'data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json'
    source_registry_path = ROOT / 'data/raw/mutual_funds/source_registry/source_registry.latest.json'
    
    if provider_profiles_path.exists():
        with open(provider_profiles_path) as f:
            provider_profiles = json.load(f)
        print(f'\nLoaded {len(provider_profiles)} provider profiles')
    else:
        provider_profiles = []
        print('Provider profiles file not found')
    
    if source_registry_path.exists():
        with open(source_registry_path) as f:
            source_registry = json.load(f)
        print(f'Loaded {len(source_registry)} source registry entries')
    else:
        source_registry = []
        print('Source registry file not found')
    
    figures = []
    
    if provider_profiles:
        pp_df = pd.DataFrame(provider_profiles)
        
        print('\nProvider Profile Status Distribution:')
        print(pp_df['status'].value_counts())
        
        print('\nDetected Strategy Distribution:')
        print(pp_df['detected_strategy'].value_counts())
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Provider Profile Status',
                'Detected Strategy Distribution',
                'Source Type Distribution',
                'Candidate Links Found per Provider'
            ),
            specs=[[{'type': 'pie'}, {'type': 'pie'}],
                   [{'type': 'pie'}, {'type': 'histogram'}]]
        )
        
        status_counts = pp_df['status'].value_counts()
        fig.add_trace(go.Pie(labels=status_counts.index, values=status_counts.values, name='Status'), row=1, col=1)
        
        strategy_counts = pp_df['detected_strategy'].value_counts()
        fig.add_trace(go.Pie(labels=strategy_counts.index, values=strategy_counts.values, name='Strategy'), row=1, col=2)
        
        source_type_counts = pp_df['source_type'].value_counts()
        fig.add_trace(go.Pie(labels=source_type_counts.index, values=source_type_counts.values, name='Source Type'), row=2, col=1)
        
        fig.add_trace(go.Histogram(x=pp_df['candidate_document_links_found'], nbinsx=20, marker_color='#17becf', name='Links'), row=2, col=2)
        
        fig.update_layout(height=800, showlegend=False, title_text='Provider Profiles Analysis')
        output_path = output_dir / 'provider_profiles.html'
        fig.write_html(str(output_path))
        figures.append(fig)
        print(f'Saved provider profiles analysis to {output_path}')
        
        # Document type hints
        all_doc_types = []
        for p in provider_profiles:
            all_doc_types.extend(p.get('document_type_hints', []))
        
        if all_doc_types:
            dt_counts = Counter(all_doc_types)
            fig = px.bar(x=list(dt_counts.values()), y=list(dt_counts.keys()), orientation='h',
                        title='Document Type Hints Across All Providers', color_discrete_sequence=['#bcbd22'])
            output_path = output_dir / 'document_type_hints.html'
            fig.write_html(str(output_path))
            figures.append(fig)
            print(f'Saved document type hints to {output_path}')
        
        # File types
        all_file_types = []
        for p in provider_profiles:
            all_file_types.extend(p.get('file_types_found', []))
        
        if all_file_types:
            ft_counts = Counter(all_file_types)
            fig = px.pie(values=list(ft_counts.values()), names=list(ft_counts.keys()), title='File Types Found Across Providers')
            output_path = output_dir / 'provider_file_types.html'
            fig.write_html(str(output_path))
            figures.append(fig)
            print(f'Saved provider file types to {output_path}')
    
    # Source Registry Analysis
    if source_registry:
        sr_df = pd.DataFrame(source_registry)
        
        print(f'\nTotal source registry entries: {len(sr_df)}')
        print(f'Enabled: {sr_df["enabled"].sum()} / {len(sr_df)}')
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Priority Distribution', 'Source Role Distribution', 'Source Type Distribution', 'Confidence Distribution'),
            specs=[[{'type': 'pie'}, {'type': 'pie'}], [{'type': 'pie'}, {'type': 'pie'}]]
        )
        
        for i, (col, title) in enumerate([('priority', 'Priority'), ('source_role', 'Source Role'), 
                                           ('source_type', 'Source Type'), ('confidence', 'Confidence')]):
            row = i // 2 + 1
            col_idx = i % 2 + 1
            counts = sr_df[col].value_counts()
            fig.add_trace(go.Pie(labels=counts.index, values=counts.values, name=title), row=row, col=col_idx)
        
        fig.update_layout(height=700, showlegend=False, title_text='Source Registry Analysis')
        output_path = output_dir / 'source_registry.html'
        fig.write_html(str(output_path))
        figures.append(fig)
        print(f'Saved source registry analysis to {output_path}')
        
        # Expected document types
        all_expected = []
        for s in source_registry:
            all_expected.extend(s.get('expected_document_types', []))
        
        if all_expected:
            exp_counts = Counter(all_expected)
            fig = px.bar(x=list(exp_counts.values()), y=list(exp_counts.keys()), orientation='h',
                        title='Expected Document Types in Source Registry', color_discrete_sequence=['#7f7f7f'])
            output_path = output_dir / 'expected_doc_types.html'
            fig.write_html(str(output_path))
            figures.append(fig)
            print(f'Saved expected doc types to {output_path}')
    
    # Cross-reference
    if provider_profiles and source_registry:
        pp_names = {p['amc_name'] for p in provider_profiles}
        sr_names = {s['amc_name'] for s in source_registry}
        
        print(f'\nProviders in profiles: {len(pp_names)}')
        print(f'Providers in source registry: {len(sr_names)}')
        print(f'In both: {len(pp_names & sr_names)}')
        print(f'Only in profiles: {len(pp_names - sr_names)}')
        print(f'Only in registry: {len(sr_names - pp_names)}')
    
    return provider_profiles, source_registry, figures


def generate_quality_report(engine, tables, provider_profiles, output_dir):
    """Generate data quality report"""
    print('\nDATA QUALITY REPORT')
    print('=' * 80)
    
    quality_checks = []
    
    # Check 1: Tables with zero rows
    for table_name in tables:
        with engine.connect() as conn:
            try:
                count = conn.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()
                if count == 0:
                    quality_checks.append({
                        'check': 'Empty Table', 'table': table_name, 'severity': 'WARNING',
                        'details': f'Table {table_name} has 0 rows'
                    })
            except Exception as e:
                quality_checks.append({
                    'check': 'Query Error', 'table': table_name, 'severity': 'ERROR', 'details': str(e)
                })
    
    # Check 2: Ingestion runs without source pages
    with engine.connect() as conn:
        try:
            runs_no_pages = conn.execute(text('''
                SELECT ir.id, ir.status FROM ingestion_runs ir
                LEFT JOIN source_pages sp ON sp.run_id = ir.id
                WHERE sp.id IS NULL
            ''')).fetchall()
            for run in runs_no_pages:
                quality_checks.append({
                    'check': 'Run Without Source Pages', 'table': 'ingestion_runs', 'severity': 'WARNING',
                    'details': f'Run {run[0]} (status: {run[1]}) has no source pages'
                })
        except Exception:
            pass
    
    # Check 3: Non-retryable quarantine
    with engine.connect() as conn:
        try:
            non_retryable = conn.execute(text('SELECT COUNT(*) FROM quarantine_rows WHERE retryable = false')).scalar()
            if non_retryable > 0:
                quality_checks.append({
                    'check': 'Non-Retryable Quarantine', 'table': 'quarantine_rows', 'severity': 'WARNING',
                    'details': f'{non_retryable} quarantine rows marked as non-retryable'
                })
        except Exception:
            pass
    
    # Check 4: Provider profiles
    if provider_profiles:
        failed_providers = [p for p in provider_profiles if p['status'] == 'failed']
        manual_review = [p for p in provider_profiles if p['status'] == 'manual_review_required']
        
        if failed_providers:
            quality_checks.append({
                'check': 'Failed Provider Profiles', 'table': 'provider_profiles (JSON)', 'severity': 'WARNING',
                'details': f'{len(failed_providers)} providers failed profiling'
            })
        if manual_review:
            quality_checks.append({
                'check': 'Providers Needing Manual Review', 'table': 'provider_profiles (JSON)', 'severity': 'INFO',
                'details': f'{len(manual_review)} providers require manual review'
            })
    
    if quality_checks:
        q_df = pd.DataFrame(quality_checks)
        severity_colors = {'ERROR': '#d62728', 'WARNING': '#ff7f0e', 'INFO': '#1f77b4'}
        
        fig = px.bar(
            q_df.groupby(['severity', 'check']).size().reset_index(name='count'),
            x='check', y='count', color='severity', color_discrete_map=severity_colors,
            title='Data Quality Checks'
        )
        fig.update_layout(xaxis_tickangle=-45, height=500)
        output_path = output_dir / 'quality_report.html'
        fig.write_html(str(output_path))
        print(f'Saved quality report to {output_path}')
        
        print('\nDetailed Quality Checks:')
        for check in quality_checks:
            icon = '🔴' if check['severity'] == 'ERROR' else '🟡' if check['severity'] == 'WARNING' else '🔵'
            print(f'{icon} [{check["severity"]}] {check["check"]} - {check["details"]}')
    else:
        print('✅ All quality checks passed!')
    
    return quality_checks


def generate_summary_dashboard(table_data, summary_data, output_dir):
    """Generate comprehensive summary dashboard"""
    print('\nCOMPREHENSIVE PIPELINE SUMMARY')
    print('=' * 80)
    
    categories = list(summary_data.keys())
    fig = make_subplots(
        rows=3, cols=3,
        subplot_titles=categories,
        specs=[[{'type': 'table'}] * 3, [{'type': 'table'}] * 3, [{'type': 'table'}] * 3]
    )
    
    for i, (category, metrics) in enumerate(summary_data.items()):
        row = i // 3 + 1
        col = i % 3 + 1
        fig.add_trace(
            go.Table(
                header=dict(values=['Metric', 'Value'], fill_color='#1f77b4', font=dict(color='white')),
                cells=dict(values=[list(metrics.keys()), list(metrics.values())], fill_color='#f8f9fa')
            ),
            row=row, col=col
        )
    
    fig.update_layout(height=1000, title_text='Pipeline Summary Dashboard')
    output_path = output_dir / 'summary_dashboard.html'
    fig.write_html(str(output_path))
    print(f'Saved summary dashboard to {output_path}')
    
    # Print summary
    for category, metrics in summary_data.items():
        print(f'\n📦 {category}')
        for key, value in metrics.items():
            print(f'   {key}: {value}')
    
    return fig


def export_tables_to_csv(engine, tables, output_dir):
    """Export all tables to CSV"""
    export_dir = output_dir / 'csv_exports'
    export_dir.mkdir(parents=True, exist_ok=True)
    
    exported = []
    for table_name in tables:
        try:
            with engine.connect() as conn:
                df = pd.read_sql(text(f'SELECT * FROM {table_name}'), conn)
            output_path = export_dir / f'{table_name}.csv'
            df.to_csv(output_path, index=False)
            exported.append(output_path)
            print(f'Exported {len(df)} rows from {table_name} to {output_path}')
        except Exception as e:
            print(f'Failed to export {table_name}: {e}')
    
    print(f'\nExported {len(exported)} tables to {export_dir}')
    return exported


def generate_html_report(summary_data, output_dir):
    """Generate standalone HTML report"""
    output_path = output_dir / 'data_exploration_report.html'
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Mutual Fund Ingestion Pipeline - Data Exploration Report</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
        h1 {{ color: #1f77b4; }}
        .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 20px 0; background: #fafafa; }}
        .metric {{ display: inline-block; margin: 10px 20px; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #1f77b4; }}
        .metric-label {{ color: #666; }}
    </style>
</head>
<body>
    <h1>📊 Mutual Fund Ingestion Pipeline - Data Exploration Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <div class="card">
        <h2>Summary Metrics</h2>
"""
    
    for category, metrics in summary_data.items():
        html_content += f'<h3>{category}</h3><div>'
        for key, value in metrics.items():
            html_content += f'<div class="metric"><div class="metric-value">{value}</div><div class="metric-label">{key}</div></div>'
        html_content += '</div>'
    
    html_content += """        </div>
</body>
</html>"""
    
    output_path.write_text(html_content)
    print(f'HTML report saved to {output_path}')
    return output_path


def main():
    """Main execution function"""
    print('=' * 80)
    print('COMPREHENSIVE DATA EXPLORATION - MUTUAL FUND INGESTION PIPELINE')
    print('=' * 80)
    
    # Setup output directory
    output_dir = ROOT / 'data/reports/mutual_funds/exploration'
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f'Output directory: {output_dir}')
    
    # Setup database
    engine, Session, DATABASE_URL = setup_database()
    
    # 1. Schema inspection
    df_tables, tables, inspector = inspect_schema(engine)
    create_schema_visualization(df_tables, output_dir)
    create_erd_visualization(inspector, tables, output_dir)
    
    # 2. Load table data
    table_data = analyze_pipeline_tables(engine, inspector, tables, output_dir)
    
    # Extract key dataframes
    runs_df = table_data.get('ingestion_runs', pd.DataFrame())
    source_pages_df = table_data.get('source_pages', pd.DataFrame())
    links_df = table_data.get('discovered_links', pd.DataFrame())
    candidates_df = table_data.get('dataset_candidates', pd.DataFrame())
    artifacts_df = table_data.get('raw_artifacts', pd.DataFrame())
    validation_df = table_data.get('validation_results', pd.DataFrame())
    quarantine_df = table_data.get('quarantine_rows', pd.DataFrame())
    retry_df = table_data.get('retry_queue', pd.DataFrame())
    amcs_df = table_data.get('amcs', pd.DataFrame())
    schemes_df = table_data.get('schemes', pd.DataFrame())
    nav_df = table_data.get('nav_history', pd.DataFrame())
    snapshots_df = table_data.get('portfolio_snapshots', pd.DataFrame())
    holdings_df = table_data.get('portfolio_holdings', pd.DataFrame())
    
    # 3. Generate visualizations
    print('\n' + '=' * 80)
    print('GENERATING VISUALIZATIONS')
    print('=' * 80)
    
    analyze_ingestion_runs(runs_df, output_dir)
    analyze_source_pages(source_pages_df, output_dir)
    analyze_discovered_links(links_df, candidates_df, output_dir)
    analyze_raw_artifacts(artifacts_df, output_dir)
    analyze_canonical_data(amcs_df, schemes_df, nav_df, snapshots_df, holdings_df, output_dir)
    analyze_validation_quarantine(validation_df, quarantine_df, retry_df, output_dir)
    provider_profiles, source_registry, pp_figs = analyze_provider_profiles(output_dir)
    
    # 4. Quality report
    quality_checks = generate_quality_report(engine, tables, provider_profiles, output_dir)
    
    # 5. Summary dashboard
    summary_data = {
        'Database': {
            'Total Tables': len(tables),
            'Total Rows (Pipeline)': int(df_tables[df_tables['table_name'].isin([
                'ingestion_runs', 'source_pages', 'discovered_links', 'dataset_candidates',
                'raw_artifacts', 'staging_rows', 'validation_results', 'quarantine_rows', 'retry_queue'
            ])]['row_count'].sum()),
            'Total Rows (Canonical)': int(df_tables[df_tables['table_name'].isin([
                'amcs', 'schemes', 'nav_history', 'documents', 'instruments',
                'portfolio_snapshots', 'portfolio_holdings'
            ])]['row_count'].sum()),
        },
        'Ingestion Runs': {
            'Total Runs': len(runs_df),
            'Completed Runs': len(runs_df[runs_df['status'] == 'completed']) if not runs_df.empty else 0,
            'Total Pages Crawled': int(runs_df['pages_seen'].sum()) if not runs_df.empty else 0,
            'Total Files Downloaded': int(runs_df['files_seen'].sum()) if not runs_df.empty else 0,
        },
        'Discovery': {
            'Total Links Discovered': len(links_df),
            'Total Candidates': len(candidates_df),
            'Unique Providers': int(candidates_df['provider_hint'].nunique()) if not candidates_df.empty else 0,
        },
        'Processing': {
            'Raw Artifacts': len(artifacts_df),
            'Retained Artifacts': int(artifacts_df['retained'].sum()) if not artifacts_df.empty else 0,
        },
        'Canonical Data': {
            'AMCs': len(amcs_df),
            'Schemes': len(schemes_df),
            'NAV Records': len(nav_df),
            'Portfolio Snapshots': len(snapshots_df),
            'Holdings': len(holdings_df),
        },
        'Quality': {
            'Validation Results': len(validation_df),
            'Quarantine Rows': len(quarantine_df),
            'Retry Queue': len(retry_df),
            'Quality Issues': len(quality_checks),
        },
        'Provider Intelligence': {
            'Profiled Providers': len(provider_profiles),
            'Successful Profiles': len([p for p in provider_profiles if p.get('status') == 'success']),
            'Failed Profiles': len([p for p in provider_profiles if p.get('status') == 'failed']),
            'Manual Review Needed': len([p for p in provider_profiles if p.get('status') == 'manual_review_required']),
            'Source Registry Entries': len(source_registry),
            'Enabled Sources': len([s for s in source_registry if s.get('enabled', False)]),
        }
    }
    
    generate_summary_dashboard(table_data, summary_data, output_dir)
    
    # 6. Export data
    print('\n' + '=' * 80)
    print('EXPORTING DATA')
    print('=' * 80)
    export_tables_to_csv(engine, tables, output_dir)
    generate_html_report(summary_data, output_dir)
    
    # 7. Final recommendations
    print('\n' + '=' * 80)
    print('NEXT STEPS & RECOMMENDATIONS')
    print('=' * 80)
    
    failed_count = len([p for p in provider_profiles if p.get('status') == 'failed'])
    manual_count = len([p for p in provider_profiles if p.get('status') == 'manual_review_required'])
    success_count = len([p for p in provider_profiles if p.get('status') == 'success'])
    
    print(f'''
Based on this exploration, here are key action items:

1. **Data Completeness**
   - Check why some canonical tables (nav_history, portfolio_holdings) may be empty
   - Verify Phase 2+ pipeline stages are running correctly

2. **Provider Coverage**
   - {failed_count} providers failed profiling - investigate root causes
   - {manual_count} providers need manual review - prioritize high-AUM AMCs
   - {success_count} providers successfully profiled - ready for Phase 2 discovery

3. **Pipeline Health**
   - Monitor quarantine_rate - should be < 10% for healthy pipeline
   - Track insertion_rate - target > 90%
   - Review failed validation checks for systematic issues

4. **Performance Optimization**
   - Links per page ratio indicates discovery efficiency
   - Candidates per link shows classification precision
   - Consider parallel processing for high-volume runs

5. **Data Quality**
   - Run validation checks regularly
   - Set up alerts for non-retryable quarantine items
   - Monitor retry queue for stuck items

6. **Output Files Generated in {output_dir}**:
   - schema_overview.html - Database schema table
   - erd_sankey.html - Entity relationship diagram
   - ingestion_runs_analysis.html - Run timeline and status
   - source_pages_analysis.html - Source page breakdown
   - discovered_links_analysis.html - Link discovery metrics
   - dataset_candidates_analysis.html - Candidate classification
   - raw_artifacts_analysis.html - Download artifacts
   - retention_rate.html - File retention rates
   - amcs.html, scheme_categories.html, schemes_per_amc.html - AMC/Scheme data
   - nav_trends.html, nav_distribution.html - NAV analysis
   - holdings_sectors.html, holdings_asset_class.html, holdings_market_value.html - Holdings
   - validation_by_severity.html, failed_checks.html - Validation
   - quarantine_reasons.html, quarantine_by_type.html - Quarantine
   - provider_profiles.html, document_type_hints.html, provider_file_types.html - Providers
   - source_registry.html, expected_doc_types.html - Source registry
   - quality_report.html - Data quality checks
   - summary_dashboard.html - Overall summary
   - data_exploration_report.html - Standalone HTML report
   - csv_exports/ - All tables as CSV files
''')
    
    print('\n✅ Data exploration complete!')
    print(f'📁 All outputs saved to: {output_dir}')


if __name__ == '__main__':
    main()