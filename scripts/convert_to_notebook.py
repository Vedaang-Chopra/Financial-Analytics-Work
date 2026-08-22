#!/usr/bin/env python3
"""
Convert the exploration script to a proper Jupyter notebook (.ipynb)
"""
import nbformat as nbf
from pathlib import Path

# Read the Python script
script_path = Path("/Users/vedaangchopra/all_data/complete_technical_work/all_projects_implemented/Financial Analytics Work/notebooks/mutual_fund_ingestion/04_comprehensive_data_exploration.py")
with open(script_path) as f:
    script_content = f.read()

# Split into logical sections for notebook cells
sections = [
    ("# Setup & Imports", """import sys
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

# Configure Plotly for notebook
pio.renderers.default = 'notebook'

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(name)s: %(message)s'
)
logger = logging.getLogger('data_exploration')"""),
    ("# Find Repo Root & Import Project Modules", """def find_repo_root():
    root = Path('.').resolve()
    while not (root / 'AGENTS.md').exists() and root != root.parent:
        root = root.parent
    return root

ROOT = find_repo_root()
sys.path.insert(0, str(ROOT))

# Import project modules
from mutual_fund_ingestion.agent.db import create_tables, get_session_maker
from mutual_fund_ingestion.agent.config import AgentConfig

print(f'[SETUP] Repository root: {ROOT}')"""),
    ("# Database Connection Setup", """# DSN resolution: DATABASE_URL env var > api.env (db_config.py) > local default
import sys as _sys
_sys.path.insert(0, str(ROOT))

from db_config import generic_database_url

DATABASE_URL = generic_database_url()

# For offline/demo mode, use SQLite
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
    print(f'[DB] Connection verified: {result}')"""),
    ("# 1. Schema Overview - All 17 Tables", """# Inspect all tables in the database
inspector = sa_inspect(engine)
tables = inspector.get_table_names()

print(f'Total tables in database: {len(tables)}')
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
    
    print(f'\\n📋 {table_name}')
    print(f'   Columns: {len(columns)} | Indexes: {len(indexes)} | FKs: {len(foreign_keys)} | Rows: {count}')
    for col in columns:
        nullable = 'NULL' if col['nullable'] else 'NOT NULL'
        default = f' DEFAULT {col[\"default\"]}' if col['default'] is not None else ''
        print(f'   - {col[\"name\"]}: {col[\"type\"]} {nullable}{default}')

# Create summary DataFrame
df_tables = pd.DataFrame(table_info)
print('\\n' + '=' * 60)
print('TABLE SUMMARY')
print(df_tables.to_string(index=False))"""),
    ("# 2. Interactive Table Schema Visualization", """# Create interactive table schema visualization
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
    title='Database Schema Overview - All 17 Tables',
    height=600,
    margin=dict(l=20, r=20, t=50, b=20)
)

fig.show()"""),
    ("# 3. Entity Relationship Diagram", """# Build ERD from foreign keys
print('ENTITY RELATIONSHIP MAP')
print('=' * 80)

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
if not df_relationships.empty:
    for _, rel in df_relationships.iterrows():
        print(f'{rel[\"from_table\"]}.{rel[\"from_column\"]} ────► {rel[\"to_table\"]}.{rel[\"to_column\"]}')
else:
    print('No foreign key relationships found')

# Visual ERD using Plotly Sankey
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
    fig_sankey.show()"""),
    ("# 4. Core Pipeline Tables - Deep Dive", """# Focus on key pipeline tables
pipeline_tables = [
    'ingestion_runs', 'source_pages', 'discovered_links', 'dataset_candidates',
    'raw_artifacts', 'staging_rows', 'validation_results', 'quarantine_rows', 'retry_queue'
]

canonical_tables = [
    'amcs', 'schemes', 'nav_history', 'documents', 'instruments',
    'portfolio_snapshots', 'portfolio_holdings'
]

print('PIPELINE TABLES DETAIL')
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
    
    print(f'\\n📊 {table_name} ({count} rows)')
    print(f'   Columns: {", ".join([c[\"name\"] for c in columns])}')
    
    if sample:
        print('   Sample rows:')
        for row in sample:
            row_str = ', '.join([f'{k}={str(v)[:50]}' for k, v in row.items()])
            print(f'     {row_str}')
    
    # Load full data for analysis
    if table_name in ['ingestion_runs', 'source_pages', 'discovered_links', 'dataset_candidates',
                      'raw_artifacts', 'validation_results', 'quarantine_rows', 'retry_queue',
                      'amcs', 'schemes', 'nav_history', 'portfolio_snapshots', 'portfolio_holdings']:
        with engine.connect() as conn:
            try:
                df = pd.read_sql(text(f'SELECT * FROM {table_name}'), conn)
                table_data[table_name] = df
            except Exception as e:
                print(f'   Failed to load: {e}')"""),
    ("# 5. Ingestion Runs Timeline & Status", """runs_df = table_data.get('ingestion_runs', pd.DataFrame())

if not runs_df.empty:
    print(f'Total ingestion runs: {len(runs_df)}')
    
    status_counts = runs_df['status'].value_counts()
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Run Status Distribution', 'Pages vs Files per Run'),
        specs=[[{'type': 'pie'}, {'type': 'scatter'}]]
    )
    
    fig.add_trace(
        go.Pie(
            labels=status_counts.index,
            values=status_counts.values,
            name='Status',
            textinfo='label+percent+value'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=runs_df['pages_seen'],
            y=runs_df['files_seen'],
            mode='markers+text',
            text=runs_df['id'].astype(str).str[:8],
            textposition='top center',
            marker=dict(
                size=12,
                color=runs_df['rows_inserted'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title='Rows Inserted')
            ),
            name='Runs'
        ),
        row=1, col=2
    )
    
    fig.update_layout(height=500, title_text='Ingestion Runs Analysis')
    fig.show()
    
    print(runs_df[['id', 'status', 'started_at', 'finished_at', 'pages_seen', 'files_seen', 'rows_inserted', 'rows_rejected']].to_string(index=False))
else:
    print('No ingestion runs found in database')"""),
    ("# 6. Source Pages Analysis", """source_pages_df = table_data.get('source_pages', pd.DataFrame())

if not source_pages_df.empty:
    print(f'Total source pages: {len(source_pages_df)}')
    
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
    fig.show()
    
    if 'source_authority_type' in source_pages_df.columns:
        auth_counts = source_pages_df['source_authority_type'].value_counts()
        print('\\nSource Authority Type Distribution:')
        print(auth_counts)
else:
    print('No source pages found')"""),
    ("# 7. Discovered Links & Dataset Candidates", """links_df = table_data.get('discovered_links', pd.DataFrame())
candidates_df = table_data.get('dataset_candidates', pd.DataFrame())

print(f'Discovered links: {len(links_df)}')
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
    fig.show()
    
    if links_df['relevance_score'].notna().any():
        fig_hist = px.histogram(
            links_df.dropna(subset=['relevance_score']),
            x='relevance_score', nbins=20, title='Relevance Score Distribution'
        )
        fig_hist.show()

if not candidates_df.empty:
    print('\\nDataset Candidates Detail:')
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
    fig.show()"""),
    ("# 8. Raw Artifacts & Download Analysis", """artifacts_df = table_data.get('raw_artifacts', pd.DataFrame())

if not artifacts_df.empty:
    print(f'Total raw artifacts: {len(artifacts_df)}')
    print(f'Retained: {artifacts_df[\"retained\"].sum()} / {len(artifacts_df)}')
    
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
    fig.show()
    
    # Retention analysis
    retained_by_type = artifacts_df.groupby('file_type')['retained'].agg(['sum', 'count']).reset_index()
    retained_by_type.columns = ['file_type', 'retained', 'total']
    retained_by_type['retention_rate'] = retained_by_type['retained'] / retained_by_type['total'] * 100
    
    fig_ret = px.bar(
        retained_by_type, x='file_type', y='retention_rate',
        title='Retention Rate by File Type (%)', text='retention_rate'
    )
    fig_ret.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_ret.show()
else:
    print('No raw artifacts found')"""),
    ("# 9. Canonical Data - AMCs, Schemes, NAV History", """amcs_df = table_data.get('amcs', pd.DataFrame())
schemes_df = table_data.get('schemes', pd.DataFrame())
nav_df = table_data.get('nav_history', pd.DataFrame())
snapshots_df = table_data.get('portfolio_snapshots', pd.DataFrame())
holdings_df = table_data.get('portfolio_holdings', pd.DataFrame())

print(f'AMCs: {len(amcs_df)}')
print(f'Schemes: {len(schemes_df)}')
print(f'NAV History records: {len(nav_df)}')
print(f'Portfolio Snapshots: {len(snapshots_df)}')
print(f'Portfolio Holdings: {len(holdings_df)}')

# AMC visualization
if not amcs_df.empty:
    fig = px.bar(amcs_df, x='name', title='Registered AMCs', color_discrete_sequence=['#1f77b4'])
    fig.update_layout(xaxis_tickangle=-45, height=400)
    fig.show()

# Scheme category distribution
if not schemes_df.empty and 'category' in schemes_df.columns:
    cat_counts = schemes_df['category'].value_counts()
    fig = px.pie(values=cat_counts.values, names=cat_counts.index, title='Scheme Category Distribution')
    fig.show()
    
    schemes_per_amc = schemes_df.groupby('amc_id').size().reset_index(name='count')
    schemes_per_amc = schemes_per_amc.merge(amcs_df[['id', 'name']], left_on='amc_id', right_on='id', how='left')
    
    fig = px.bar(
        schemes_per_amc.sort_values('count', ascending=True),
        x='count', y='name', orientation='h',
        title='Number of Schemes per AMC', color_discrete_sequence=['#2ca02c']
    )
    fig.show()

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
    
    fig.update_layout(
        title='NAV Trends - Top 5 Schemes by Record Count',
        xaxis_title='Date', yaxis_title='NAV Value', height=500, hovermode='x unified'
    )
    fig.show()
    
    fig_hist = px.histogram(nav_df.dropna(subset=['nav_value']), x='nav_value', nbins=50, title='NAV Value Distribution')
    fig_hist.show()

# Portfolio holdings analysis
if not holdings_df.empty:
    if 'sector' in holdings_df.columns:
        sector_counts = holdings_df['sector'].value_counts().head(15)
        fig = px.bar(x=sector_counts.values, y=sector_counts.index, orientation='h',
                    title='Top 15 Sectors in Portfolio Holdings', color_discrete_sequence=['#e377c2'])
        fig.show()
    
    if 'asset_class' in holdings_df.columns:
        asset_counts = holdings_df['asset_class'].value_counts()
        fig = px.pie(values=asset_counts.values, names=asset_counts.index, title='Asset Class Distribution in Holdings')
        fig.show()
    
    if 'market_value' in holdings_df.columns:
        holdings_df['market_value'] = pd.to_numeric(holdings_df['market_value'], errors='coerce')
        mv_df = holdings_df.dropna(subset=['market_value'])
        if not mv_df.empty:
            fig = px.histogram(mv_df, x='market_value', nbins=50, title='Market Value Distribution (INR)', log_y=True)
            fig.show()"""),
    ("# 10. Validation & Quarantine Analysis", """validation_df = table_data.get('validation_results', pd.DataFrame())
quarantine_df = table_data.get('quarantine_rows', pd.DataFrame())
retry_df = table_data.get('retry_queue', pd.DataFrame())

print(f'Validation results: {len(validation_df)}')
print(f'Quarantine rows: {len(quarantine_df)}')
print(f'Retry queue items: {len(retry_df)}')

if not validation_df.empty:
    val_status = validation_df.groupby(['severity', 'status']).size().reset_index(name='count')
    
    fig = px.bar(
        val_status, x='severity', y='count', color='status',
        title='Validation Results by Severity and Status', barmode='stack',
        color_discrete_map={'passed': '#2ca02c', 'failed': '#d62728', 'warning': '#ff7f0e'}
    )
    fig.show()
    
    failed_checks = validation_df[validation_df['status'] == 'failed']['check_name'].value_counts().head(15)
    if not failed_checks.empty:
        fig = px.bar(x=failed_checks.values, y=failed_checks.index, orientation='h',
                    title='Top 15 Failed Validation Checks', color_discrete_sequence=['#d62728'])
        fig.show()
    else:
        print('No failed validation checks - all validations passed')
    
    entity_counts = validation_df['entity_type'].value_counts()
    fig = px.pie(values=entity_counts.values, names=entity_counts.index, title='Validation by Entity Type')
    fig.show()

if not quarantine_df.empty:
    reason_counts = quarantine_df['reason'].value_counts().head(20)
    fig = px.bar(x=reason_counts.values, y=reason_counts.index, orientation='h',
                title='Top 20 Quarantine Reasons', color_discrete_sequence=['#8c564b'])
    fig.update_layout(height=600)
    fig.show()
    
    if 'dataset_type' in quarantine_df.columns:
        q_dt_counts = quarantine_df['dataset_type'].value_counts()
        fig = px.pie(values=q_dt_counts.values, names=q_dt_counts.index, title='Quarantine by Dataset Type')
        fig.show()
    
    retryable_counts = quarantine_df['retryable'].value_counts()
    fig = px.pie(
        values=retryable_counts.values,
        names=['Retryable' if r else 'Not Retryable' for r in retryable_counts.index],
        title='Quarantine: Retryable vs Non-Retryable'
    )
    fig.show()

if not retry_df.empty:
    retry_status = retry_df['status'].value_counts()
    fig = px.pie(values=retry_status.values, names=retry_status.index, title='Retry Queue Status')
    fig.show()
    
    fig = px.histogram(retry_df, x='retry_count', nbins=10, title='Retry Count Distribution')
    fig.show()
    
    task_counts = retry_df['task_type'].value_counts()
    fig = px.bar(x=task_counts.index, y=task_counts.values, title='Retry Queue by Task Type')
    fig.show()"""),
    ("# 11. Provider Profiles Analysis (JSON artifacts)", """# Load provider profiles from JSON artifacts
provider_profiles_path = ROOT / 'data/raw/mutual_funds/provider_profiles/provider_profiles.latest.json'
source_registry_path = ROOT / 'data/raw/mutual_funds/source_registry/source_registry.latest.json'

if provider_profiles_path.exists():
    with open(provider_profiles_path) as f:
        provider_profiles = json.load(f)
    print(f'Loaded {len(provider_profiles)} provider profiles')
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

# Analyze provider profiles
if provider_profiles:
    pp_df = pd.DataFrame(provider_profiles)
    
    print('\\nProvider Profile Status Distribution:')
    print(pp_df['status'].value_counts())
    
    print('\\nDetected Strategy Distribution:')
    print(pp_df['detected_strategy'].value_counts())
    
    print('\\nSource Type Distribution:')
    print(pp_df['source_type'].value_counts())
    
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
    fig.show()
    
    # Document type hints
    all_doc_types = []
    for p in provider_profiles:
        all_doc_types.extend(p.get('document_type_hints', []))
    
    if all_doc_types:
        dt_counts = Counter(all_doc_types)
        fig = px.bar(x=list(dt_counts.values()), y=list(dt_counts.keys()), orientation='h',
                    title='Document Type Hints Across All Providers', color_discrete_sequence=['#bcbd22'])
        fig.show()
    
    # File types
    all_file_types = []
    for p in provider_profiles:
        all_file_types.extend(p.get('file_types_found', []))
    
    if all_file_types:
        ft_counts = Counter(all_file_types)
        fig = px.pie(values=list(ft_counts.values()), names=list(ft_counts.keys()), title='File Types Found Across Providers')
        fig.show()
    
    # Providers requiring JavaScript
    js_required = pp_df[pp_df['requires_javascript'] == True]
    print(f'\\nProviders requiring JavaScript: {len(js_required)}')
    if len(js_required) > 0:
        print(js_required[['amc_name', 'detected_strategy', 'seed_url']].to_string(index=False))"""),
    ("# 12. Source Registry Analysis", """if source_registry:
    sr_df = pd.DataFrame(source_registry)
    
    print(f'Total source registry entries: {len(sr_df)}')
    print(f'Enabled: {sr_df[\"enabled\"].sum()} / {len(sr_df)}')
    
    print('\\nPriority Distribution:')
    print(sr_df['priority'].value_counts())
    
    print('\\nSource Role Distribution:')
    print(sr_df['source_role'].value_counts())
    
    print('\\nSource Type Distribution:')
    print(sr_df['source_type'].value_counts())
    
    print('\\nConfidence Distribution:')
    print(sr_df['confidence'].value_counts())
    
    # Expected document types
    all_expected = []
    for s in source_registry:
        all_expected.extend(s.get('expected_document_types', []))
    
    if all_expected:
        exp_counts = Counter(all_expected)
        fig = px.bar(x=list(exp_counts.values()), y=list(exp_counts.keys()), orientation='h',
                    title='Expected Document Types in Source Registry', color_discrete_sequence=['#7f7f7f'])
        fig.show()
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Priority Distribution', 'Source Role Distribution', 'Source Type Distribution', 'Confidence Distribution'),
        specs=[[{'type': 'pie'}, {'type': 'pie'}],
               [{'type': 'pie'}, {'type': 'pie'}]]
    )
    
    for i, (col, title) in enumerate([('priority', 'Priority'), ('source_role', 'Source Role'), 
                                       ('source_type', 'Source Type'), ('confidence', 'Confidence')]):
        row = i // 2 + 1
        col_idx = i % 2 + 1
        counts = sr_df[col].value_counts()
        fig.add_trace(go.Pie(labels=counts.index, values=counts.values, name=title), row=row, col=col_idx)
    
    fig.update_layout(height=700, showlegend=False, title_text='Source Registry Analysis')
    fig.show()
    
    # Manual overrides
    all_overrides = []
    for s in source_registry:
        all_overrides.extend(s.get('manual_overrides', []))
    
    if all_overrides:
        ov_counts = Counter(all_overrides)
        fig = px.bar(x=list(ov_counts.keys()), y=list(ov_counts.values()),
                    title='Manual Overrides Applied', color_discrete_sequence=['#ff7f0e'])
        fig.show()"""),
    ("# 13. Cross-Reference: Provider Profiles vs Source Registry", """if provider_profiles and source_registry:
    pp_names = {p['amc_name'] for p in provider_profiles}
    sr_names = {s['amc_name'] for s in source_registry}
    
    print(f'Providers in profiles: {len(pp_names)}')
    print(f'Providers in source registry: {len(sr_names)}')
    print(f'In both: {len(pp_names & sr_names)}')
    print(f'Only in profiles: {len(pp_names - sr_names)}')
    print(f'Only in registry: {len(sr_names - pp_names)}')
    
    # Venn diagram style visualization
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=[0], y=[0],
        mode='markers+text',
        marker=dict(size=100, color='#1f77b4', opacity=0.5),
        text=['Provider Profiles'],
        textposition='middle center',
        name=f'Profiles ({len(pp_names)})'
    ))
    
    fig.add_trace(go.Scatter(
        x=[1], y=[0],
        mode='markers+text',
        marker=dict(size=100, color='#ff7f0e', opacity=0.5),
        text=['Source Registry'],
        textposition='middle center',
        name=f'Registry ({len(sr_names)})'
    ))
    
    fig.add_trace(go.Scatter(
        x=[0.5], y=[0],
        mode='markers+text',
        marker=dict(size=60, color='#2ca02c', opacity=0.7),
        text=[f'Both\\n({len(pp_names & sr_names)})'],
        textposition='middle center',
        name=f'Overlap ({len(pp_names & sr_names)})'
    ))
    
    fig.update_layout(
        title='Provider Coverage: Profiles vs Source Registry',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=300,
        showlegend=True
    )
    fig.show()
    
    # Status of providers in both
    common = pp_names & sr_names
    if common:
        common_profiles = [p for p in provider_profiles if p['amc_name'] in common]
        status_in_common = Counter(p['status'] for p in common_profiles)
        strategy_in_common = Counter(p['detected_strategy'] for p in common_profiles)
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Status of Common Providers', 'Strategy of Common Providers'),
            specs=[[{'type': 'domain'}, {'type': 'domain'}]]
        )
        
        fig.add_trace(go.Pie(labels=list(status_in_common.keys()), values=list(status_in_common.values()), name='Status'), row=1, col=1)
        fig.add_trace(go.Pie(labels=list(strategy_in_common.keys()), values=list(strategy_in_common.values()), name='Strategy'), row=1, col=2)
        
        fig.update_layout(height=400, title_text='Common Providers Analysis')
        fig.show()"""),
    ("# 14. Data Quality Report", """print('DATA QUALITY REPORT')
print('=' * 80)

quality_checks = []

# Check 1: Tables with zero rows
for table_name in tables:
    with engine.connect() as conn:
        try:
            count = conn.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()
            if count == 0:
                quality_checks.append({
                    'check': 'Empty Table',
                    'table': table_name,
                    'severity': 'WARNING',
                    'details': f'Table {table_name} has 0 rows'
                })
        except Exception as e:
            quality_checks.append({
                'check': 'Query Error',
                'table': table_name,
                'severity': 'ERROR',
                'details': str(e)
            })

# Check 2: Ingestion runs without source pages
with engine.connect() as conn:
    try:
        runs_no_pages = conn.execute(text('''
            SELECT ir.id, ir.status 
            FROM ingestion_runs ir
            LEFT JOIN source_pages sp ON sp.run_id = ir.id
            WHERE sp.id IS NULL
        ''')).fetchall()
        for run in runs_no_pages:
            quality_checks.append({
                'check': 'Run Without Source Pages',
                'table': 'ingestion_runs',
                'severity': 'WARNING',
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
                'check': 'Non-Retryable Quarantine',
                'table': 'quarantine_rows',
                'severity': 'WARNING',
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
            'check': 'Failed Provider Profiles',
            'table': 'provider_profiles (JSON)',
            'severity': 'WARNING',
            'details': f'{len(failed_providers)} providers failed profiling'
        })
    
    if manual_review:
        quality_checks.append({
            'check': 'Providers Needing Manual Review',
            'table': 'provider_profiles (JSON)',
            'severity': 'INFO',
            'details': f'{len(manual_review)} providers require manual review'
        })

# Display quality report
if quality_checks:
    q_df = pd.DataFrame(quality_checks)
    
    severity_colors = {'ERROR': '#d62728', 'WARNING': '#ff7f0e', 'INFO': '#1f77b4'}
    
    fig = px.bar(
        q_df.groupby(['severity', 'check']).size().reset_index(name='count'),
        x='check', y='count', color='severity', color_discrete_map=severity_colors,
        title='Data Quality Checks'
    )
    fig.update_layout(xaxis_tickangle=-45, height=500)
    fig.show()
    
    print('\\nDetailed Quality Checks:')
    for check in quality_checks:
        icon = '🔴' if check['severity'] == 'ERROR' else '🟡' if check['severity'] == 'WARNING' else '🔵'
        print(f'{icon} [{check[\"severity\"]}] {check[\"check\"]} - {check[\"details\"]}')
else:
    print('✅ All quality checks passed!')"""),
    ("# 15. Pipeline Performance Metrics", """with engine.connect() as conn:
    perf_df = pd.read_sql(text('''
        SELECT
            ir.id as run_id,
            ir.status,
            ir.started_at,
            ir.finished_at,
            ir.pages_seen,
            ir.files_seen,
            ir.rows_inserted,
            ir.rows_rejected,
            (SELECT COUNT(*) FROM source_pages sp WHERE sp.run_id = ir.id) as actual_source_pages,
            (SELECT COUNT(*) FROM discovered_links dl WHERE dl.run_id = ir.id) as actual_discovered_links,
            (SELECT COUNT(*) FROM dataset_candidates dc WHERE dc.run_id = ir.id) as actual_candidates,
            (SELECT COUNT(*) FROM raw_artifacts ra WHERE ra.run_id = ir.id) as actual_artifacts,
            (SELECT COUNT(*) FROM staging_rows sr WHERE sr.run_id = ir.id) as actual_staging_rows,
            (SELECT COUNT(*) FROM validation_results vr WHERE vr.run_id = ir.id) as actual_validations,
            (SELECT COUNT(*) FROM quarantine_rows qr WHERE qr.run_id = ir.id) as actual_quarantine
        FROM ingestion_runs ir
        ORDER BY ir.started_at DESC
    '''), conn)

if not perf_df.empty:
    perf_df['started_at'] = pd.to_datetime(perf_df['started_at'])
    perf_df['finished_at'] = pd.to_datetime(perf_df['finished_at'])
    perf_df['duration_seconds'] = (perf_df['finished_at'] - perf_df['started_at']).dt.total_seconds()
    
    perf_df['links_per_page'] = perf_df['actual_discovered_links'] / perf_df['actual_source_pages'].replace(0, np.nan)
    perf_df['candidates_per_link'] = perf_df['actual_candidates'] / perf_df['actual_discovered_links'].replace(0, np.nan)
    perf_df['artifacts_per_candidate'] = perf_df['actual_artifacts'] / perf_df['actual_candidates'].replace(0, np.nan)
    perf_df['staging_per_artifact'] = perf_df['actual_staging_rows'] / perf_df['actual_artifacts'].replace(0, np.nan)
    perf_df['insertion_rate'] = perf_df['rows_inserted'] / (perf_df['rows_inserted'] + perf_df['rows_rejected']).replace(0, np.nan)
    perf_df['quarantine_rate'] = perf_df['actual_quarantine'] / perf_df['actual_staging_rows'].replace(0, np.nan)
    
    print('Pipeline Performance Metrics:')
    cols = ['run_id', 'status', 'duration_seconds', 'pages_seen', 'actual_source_pages',
            'actual_discovered_links', 'actual_candidates', 'actual_artifacts',
            'links_per_page', 'candidates_per_link', 'artifacts_per_candidate',
            'insertion_rate', 'quarantine_rate']
    print(perf_df[cols].to_string(index=False))
    
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=(
            'Run Duration (seconds)',
            'Links per Page',
            'Candidates per Link',
            'Artifacts per Candidate',
            'Insertion Rate',
            'Quarantine Rate'
        )
    )
    
    metrics = ['duration_seconds', 'links_per_page', 'candidates_per_link', 
               'artifacts_per_candidate', 'insertion_rate', 'quarantine_rate']
    
    for i, metric in enumerate(metrics):
        row = i // 3 + 1
        col = i % 3 + 1
        data = perf_df[metric].dropna()
        if len(data) > 0:
            fig.add_trace(
                go.Bar(x=perf_df['run_id'].astype(str).str[:8], y=data, name=metric, marker_color=px.colors.qualitative.Set1[i]),
                row=row, col=col
            )
    
    fig.update_layout(height=700, showlegend=False, title_text='Pipeline Performance Metrics')
    fig.show()"""),
    ("# 16. Summary Dashboard", """print('COMPREHENSIVE PIPELINE SUMMARY')
print('=' * 80)

summary = {
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

# Print summary
for category, metrics in summary.items():
    print(f'\\n📦 {category}')
    for key, value in metrics.items():
        print(f'   {key}: {value}')

# Visual summary cards
categories = list(summary.keys())
fig = make_subplots(
    rows=3, cols=3,
    subplot_titles=categories,
    specs=[[{'type': 'table'}] * 3, [{'type': 'table'}] * 3, [{'type': 'table'}] * 3]
)

for i, (category, metrics) in enumerate(summary.items()):
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
fig.show()"""),
    ("# 17. Export Functions", """def export_table_to_csv(table_name: str, output_dir: Path = None):
    \"\"\"Export any table to CSV\"\"\"
    if output_dir is None:
        output_dir = ROOT / 'data/reports/mutual_funds/exports'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with engine.connect() as conn:
        df = pd.read_sql(text(f'SELECT * FROM {table_name}'), conn)
    
    output_path = output_dir / f'{table_name}_{datetime.now().strftime(\"%Y%m%d_%H%M%S\")}.csv'
    df.to_csv(output_path, index=False)
    print(f'Exported {len(df)} rows to {output_path}')
    return output_path

def export_all_tables(output_dir: Path = None):
    \"\"\"Export all tables to CSV\"\"\"
    if output_dir is None:
        output_dir = ROOT / 'data/reports/mutual_funds/exports'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    exported = []
    for table_name in tables:
        try:
            path = export_table_to_csv(table_name, output_dir)
            exported.append(path)
        except Exception as e:
            print(f'Failed to export {table_name}: {e}')
    
    print(f'Exported {len(exported)} tables to {output_dir}')
    return exported

def generate_html_report(output_path: Path = None):
    \"\"\"Generate a standalone HTML report with all visualizations\"\"\"
    if output_path is None:
        output_path = ROOT / 'data/reports/mutual_funds/data_exploration_report.html'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    html_content = f\"\"\"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mutual Fund Ingestion Pipeline - Data Exploration Report</title>
        <script src=\"https://cdn.plot.ly/plotly-latest.min.js\"></script>
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
        <p>Database: {DATABASE_URL}</p>
        
        <div class=\"card\">
            <h2>Summary Metrics</h2>
    \"\"\"
    
    for category, metrics in summary.items():
        html_content += f'<h3>{category}</h3><div>'
        for key, value in metrics.items():
            html_content += f'<div class=\"metric\"><div class=\"metric-value\">{value}</div><div class=\"metric-label\">{key}</div></div>'
        html_content += '</div>'
    
    html_content += \"\"\"
        </div>
    </body>
    </html>
    \"\"\"
    
    output_path.write_text(html_content)
    print(f'HTML report saved to {output_path}')
    return output_path

print('✓ Export functions defined')
print('Available functions:')
print('  - export_table_to_csv(table_name)')
print('  - export_all_tables()')
print('  - generate_html_report()')"""),
    ("# 18. Next Steps & Recommendations", """print(f'''
NEXT STEPS & RECOMMENDATIONS
=============================

Based on this exploration, here are key action items:

1. **Data Completeness**
   - Check why some canonical tables (nav_history, portfolio_holdings) may be empty
   - Verify Phase 2+ pipeline stages are running correctly

2. **Provider Coverage**
   - {len([p for p in provider_profiles if p.get('status') == 'failed'])} providers failed profiling - investigate root causes
   - {len([p for p in provider_profiles if p.get('status') == 'manual_review_required'])} providers need manual review - prioritize high-AUM AMCs
   - {len([p for p in provider_profiles if p.get('status') == 'success'])} providers successfully profiled - ready for Phase 2 discovery

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

6. **Recommended Notebooks to Run Next**:
   - 02_agent_pipeline_inspection.ipynb - For pipeline debugging
   - 03_phase2_discovery_review.ipynb - For Phase 2 candidate analysis
   - 01a/01b_phase_1_*_review.ipynb - For provider profiling deep-dive
''')"""),
]

# Create notebook
nb = nbf.v4.new_notebook()

# Add title cell
nb.cells.append(nbf.v4.new_markdown_cell("""# Comprehensive Data Exploration & Visualization Notebook

**Purpose**: Complete end-to-end exploration of the Mutual Fund Ingestion Pipeline data.
This notebook connects to the PostgreSQL database, inspects all 17 tables, analyzes
provider profiles, source registry, and generates interactive Plotly visualizations.

**Prerequisites**: 
- DATABASE_URL environment variable set (PostgreSQL)
- Or run with SQLite for local inspection (uses temp DB)

**Outputs**: Interactive charts, summary tables, data quality reports"""))

# Add each section as code cells
for title, code in sections:
    nb.cells.append(nbf.v4.new_markdown_cell(f"## {title.replace('# ', '').replace('#', '')}"))
    nb.cells.append(nbf.v4.new_code_cell(code))

# Save notebook
output_path = Path("/Users/vedaangchopra/all_data/complete_technical_work/all_projects_implemented/Financial Analytics Work/notebooks/mutual_fund_ingestion/04_comprehensive_data_exploration.ipynb")
with open(output_path, 'w') as f:
    nbf.write(nb, f)

print(f"✅ Notebook created at: {output_path}")
print(f"📝 Total cells: {len(nb.cells)}")