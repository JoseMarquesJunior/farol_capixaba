import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd 

NOME_ARQUIVO_SETORES = "educacao/data/ES_setores_CD2022.gpkg"
NOME_ARQUIVO_DEMOGRAFICOS = "educacao/data/Agregados_por_setores_demografia_BR.xlsx"
gdf = gpd.read_file(NOME_ARQUIVO_SETORES)


dados_demograficos = pd.read_excel(
    NOME_ARQUIVO_DEMOGRAFICOS,
    #dtype={"CD_setor": str}
)
print(dados_demograficos.head())

# Índice necessário
gdf = gdf.reset_index(drop=True)

# Cor única
gdf["cor"] = 1

# GeoJSON
geojson = gdf.__geo_interface__

# Centro do mapa
centro = gdf.unary_union.centroid

# =====================================
# Plotly
# =====================================

fig = go.Figure(
    go.Choroplethmap(
        geojson=geojson,
        locations=gdf.index,
        z=gdf["cor"],
        featureidkey="id",
        colorscale=[[0, "#4F81BD"], [1, "#4F81BD"]],
        marker_line_width=0.2,
        marker_line_color="white",
        showscale=False,
        customdata=gdf[
            [
                "CD_SETOR",
                "NM_BAIRRO",
                "NM_MUN",
                "AREA_KM2",
                "SITUACAO",
            ]
        ],
        hovertemplate="""
<b>Setor:</b> %{customdata[0]}<br>
<b>Bairro:</b> %{customdata[1]}<br>
<b>Município:</b> %{customdata[2]}<br>
<b>Área:</b> %{customdata[3]:.3f} km²<br>
<b>Situação:</b> %{customdata[4]}
<extra></extra>
"""
    )
)

fig.update_layout(

    title="Setores Censitários",

    map=dict(
        style="carto-positron",
        center=dict(
            lat=centro.y,
            lon=centro.x
        ),
        zoom=11
    ),

    margin=dict(
        l=0,
        r=0,
        t=40,
        b=0
    )
)

fig.show()

fig.write_html("analises/setores_censitarios.html")