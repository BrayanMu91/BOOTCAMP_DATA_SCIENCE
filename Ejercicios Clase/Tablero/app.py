# ------------------------------------------------------------------------------
# 1. IMPORTACIÓN DE LIBRERÍAS
# ------------------------------------------------------------------------------
### pip install dash dash-bootstrap-components plotly pandas kagglehub pycountry

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import kagglehub
import pycountry

# ------------------------------------------------------------------------------
# 2. CARGA Y PREPROCESAMIENTO DE DATOS
# ------------------------------------------------------------------------------
print("Iniciando aplicación...")
print("Conectando al dataset en Kaggle...")

#Conexion y lectura de datos desde el area de kaggel

try:
    df = kagglehub.load_dataset(
        adapter=kagglehub.KaggleDatasetAdapter.PANDAS,
        handle="adilshamim8/salaries-for-data-science-jobs",
        path="salaries.csv"
    )
    print("DataFrame cargado de manera exitosa desde Kaggle.")
except Exception as e:
    print(f"\nError fatal al cargar desde Kaggle: {e}\nRevisa tu conexión y configuración de API.")
    exit()

# --- Transformaciones de Datos ---
exp_map = {'EN': 'Entry-level', 'MI': 'Mid-level', 'SE': 'Senior-level', 'EX': 'Executive-level'}
df['experience_label'] = df['experience_level'].map(exp_map)

remote_map = {0: 'Presencial', 50: 'Híbrido', 100: 'Remoto Total'}
df['remote_type'] = df['remote_ratio'].map(remote_map)

# Opciones para los filtros iniciales
year_options = sorted(df['work_year'].unique())
exp_options = ['Entry-level', 'Mid-level', 'Senior-level', 'Executive-level']

# Paleta de colores
custom_colors = {'background': '#222831', 'text': '#EEEEEE', 'chart_background': '#393E46', 'accent_color': '#00ADB5'}

# ------------------------------------------------------------------------------
# 3. DISEÑO DE LA APLICACIÓN
# ------------------------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
server = app.server

app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Tablero de Salarios en Ciencia de Datos", className="text-center text-primary mb-4 pt-3"), width=12)),
    
    dbc.Row([
        dbc.Col([
            html.Label("1. Filtro por Año(s):"),
            dcc.Dropdown(id='year-filter', options=year_options, multi=True, placeholder="Todos los años")
        ], md=4),
        dbc.Col([
            html.Label("2. Filtro por Nivel de Experiencia:"),
            dcc.Dropdown(id='exp-filter', options=exp_options, multi=True, placeholder="Todos los niveles")
        ], md=4),
        dbc.Col([
            html.Label("3. Filtro por Ciudad(es) (se actualiza solo):"),
            dcc.Dropdown(id='location-filter', multi=True, placeholder="Todas las ciudades disponibles...")
        ], md=4)
    ], className="mb-4"),
    
    dbc.Row([dbc.Col(dcc.Graph(id='dist-salary-chart'), md=6), dbc.Col(dcc.Graph(id='exp-salary-chart'), md=6)], className="mb-4"),
    dbc.Row([dbc.Col(dcc.Graph(id='top-locations-chart'), md=6), dbc.Col(dcc.Graph(id='remote-salary-chart'), md=6)], className="mb-4"),
    dbc.Row([dbc.Col(dcc.Graph(id='map-chart'), md=12)], className="mb-4")
], fluid=True)

# ------------------------------------------------------------------------------
# 4. LÓGICA INTERACTIVA (CALLBACKS)
# ------------------------------------------------------------------------------

@app.callback(
    Output('location-filter', 'options'),
    [Input('year-filter', 'value'),
     Input('exp-filter', 'value')]
)
def update_location_options(selected_years, selected_exp):
    if not selected_years and not selected_exp:
        dff = df.copy()
    elif not selected_years:
        dff = df[df['experience_label'].isin(selected_exp)]
    elif not selected_exp:
        dff = df[df['work_year'].isin(selected_years)]
    else:
        dff = df[df['work_year'].isin(selected_years) & df['experience_label'].isin(selected_exp)]
        
    available_locations = sorted(dff['company_location'].unique())
    return [{'label': loc, 'value': loc} for loc in available_locations]

@app.callback(
    [Output('dist-salary-chart', 'figure'),
     Output('exp-salary-chart', 'figure'),
     Output('top-locations-chart', 'figure'),
     Output('remote-salary-chart', 'figure'),
     Output('map-chart', 'figure')],
    [Input('year-filter', 'value'),
     Input('exp-filter', 'value'),
     Input('location-filter', 'value')]
)
def update_dashboard(selected_years, selected_exp, selected_locations):
    dff = df.copy()

    if selected_years:
        dff = dff[dff['work_year'].isin(selected_years)]
    if selected_exp:
        dff = dff[dff['experience_label'].isin(selected_exp)]
    if selected_locations:
        dff = dff[dff['company_location'].isin(selected_locations)]

    def create_empty_fig(title_text):
        fig = go.Figure()
        fig.update_layout(title_text=title_text, xaxis={"visible": False}, yaxis={"visible": False},
                          annotations=[{"text": "No hay datos para la selección actual", "xref": "paper", "yref": "paper",
                                        "showarrow": False, "font": {"size": 20, "color": "white"}}],
                          template='plotly_dark')
        return fig

    if dff.empty:
        return [create_empty_fig("Gráfico")] * 5

    # --- Generación de figuras ---
    fig1 = px.histogram(dff, x='salary_in_usd', marginal='box', title='Distribución General de Salarios (USD)')
    fig2 = px.box(dff, x='experience_label', y='salary_in_usd', category_orders={'experience_label': exp_options}, title='Salario por Nivel de Experiencia')
    
    top_locs = dff.groupby('company_location')['salary_in_usd'].mean().nlargest(10).sort_values(ascending=True)
    fig3 = px.bar(top_locs, x=top_locs.values, y=top_locs.index, orientation='h', title='Top 10 Ciudades por Salario Promedio')

    fig4 = px.box(dff, x='remote_type', y='salary_in_usd', title='Salario por Modalidad de Trabajo')
    
    # --- AJUSTE EN LA AGRUPACIÓN PARA EL MAPA ---
    # 1. Ahora se agrupa y se calcula tanto el promedio como el conteo
    df_map = dff.groupby('company_location').agg(
        avg_salary=('salary_in_usd', 'mean'),
        record_count=('salary_in_usd', 'size')
    ).reset_index()

    def get_iso_alpha3(code):
        try: return pycountry.countries.get(alpha_2=code).alpha_3
        except: return None
    df_map['iso_alpha'] = df_map['company_location'].apply(get_iso_alpha3)
    
    # --- AJUSTE EN LA CREACIÓN DEL MAPA ---
    # 2. Se usa 'hover_data' para añadir el conteo y 'labels' para mejorar las etiquetas
    fig5 = px.choropleth(
        df_map,
        locations='iso_alpha',
        color='avg_salary',
        hover_name='company_location',
        hover_data={'record_count': True, 'avg_salary': ':.0f'}, # Muestra el conteo y formatea el salario
        labels={'avg_salary': 'Salario Promedio (USD)', 'record_count': 'Cantidad de Registros'},
        color_continuous_scale=px.colors.sequential.Blues,
        title='Salario Promedio por País (Mapa)'
    )
    
    # Aplicar estilo
    for fig in [fig1, fig2, fig3, fig4, fig5]:
        fig.update_layout(template='plotly_dark', plot_bgcolor=custom_colors['chart_background'], paper_bgcolor=custom_colors['chart_background'],
                          font_color=custom_colors['text'], margin=dict(l=40, r=20, t=60, b=40))
    fig5.update_layout(geo=dict(bgcolor=custom_colors['chart_background'], lakecolor=custom_colors['chart_background']))

    return fig1, fig2, fig3, fig4, fig5

# ------------------------------------------------------------------------------
# 5. EJECUCIÓN DE LA APLICACIÓN
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)