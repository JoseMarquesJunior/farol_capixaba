import geopandas as gpd
import pandas as pd 
import plotly.express as px
import plotly.graph_objects as go

def renomear_colunas_demografia(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renomeia as colunas do arquivo de agregados demográficos do IBGE
    para nomes mais descritivos.

    Retorna uma cópia do DataFrame.
    """

    mapa = {
        "V01006": "Quantidade de moradores",
        "V01007": "Sexo masculino",
        "V01008": "Sexo feminino",

        "V01009": "Homens 0 a 4 anos",
        "V01010": "Homens 5 a 9 anos",
        "V01011": "Homens 10 a 14 anos",
        "V01012": "Homens 15 a 19 anos",
        "V01013": "Homens 20 a 24 anos",
        "V01014": "Homens 25 a 29 anos",
        "V01015": "Homens 30 a 39 anos",
        "V01016": "Homens 40 a 49 anos",
        "V01017": "Homens 50 a 59 anos",
        "V01018": "Homens 60 a 69 anos",
        "V01019": "Homens 70 anos ou mais",

        "V01020": "Mulheres 0 a 4 anos",
        "V01021": "Mulheres 5 a 9 anos",
        "V01022": "Mulheres 10 a 14 anos",
        "V01023": "Mulheres 15 a 19 anos",
        "V01024": "Mulheres 20 a 24 anos",
        "V01025": "Mulheres 25 a 29 anos",
        "V01026": "Mulheres 30 a 39 anos",
        "V01027": "Mulheres 40 a 49 anos",
        "V01028": "Mulheres 50 a 59 anos",
        "V01029": "Mulheres 60 a 69 anos",
        "V01030": "Mulheres 70 anos ou mais",

        "V01031": "0 a 4 anos",
        "V01032": "5 a 9 anos",
        "V01033": "10 a 14 anos",
        "V01034": "15 a 19 anos",
        "V01035": "20 a 24 anos",
        "V01036": "25 a 29 anos",
        "V01037": "30 a 39 anos",
        "V01038": "40 a 49 anos",
        "V01039": "50 a 59 anos",
        "V01040": "60 a 69 anos",
        "V01041": "70 anos ou mais",
    }

    return df.rename(columns=mapa)

def encontrar_centroides(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    
    centroides = (
        gdf.to_crs(3857)
        .centroid
        .to_crs(4326)
    )
    gdf["latitude"] = centroides.y
    gdf["longitude"] = centroides.x
    return gdf  

def configurando_gdf_para_plotly(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Configura o GeoDataFrame para ser usado com Plotly.
    Adiciona uma coluna 'cor' com valor 1 para todos os setores.
    """
    gdf = gdf.reset_index(drop=True)
    gdf["cor"] = 1
    return gdf

def plotar_setores(gdf: gpd.GeoDataFrame) -> None:
    
    # GeoJSON
    geojson = gdf.__geo_interface__

    # Centro do mapa
    centro = gdf.geometry.union_all().centroid

    fig = go.Figure(
        go.Choroplethmap(
            geojson=geojson,
            locations=gdf.index,
            z=gdf["cor"],
            featureidkey="id",
            #colorscale=[[0, "#4F81BD"], [1, "#4F81BD"]],
            #colorscale=[[0, "#DCEAF7"], [1, "#DCEAF7"]],
            #colorscale=[[0, "#E8F1FA"], [1, "#E8F1FA"]],
            colorscale=[[0, "#69ABEE"], [1, "#E4726A"]],
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
                    "0 a 4 anos",
                    "5 a 9 anos",
                    "10 a 14 anos", 
                    "15 a 19 anos",
                ]
            ],
            hovertemplate="""
    <b>Setor:</b> %{customdata[0]}<br>
    <b>Bairro:</b> %{customdata[1]}<br>
    <b>Município:</b> %{customdata[2]}<br>
    <b>Área:</b> %{customdata[3]:.3f} km²<br>
    <b>Situação:</b> %{customdata[4]}<br>
    <b>0 a 4 anos:</b> %{customdata[5]}<br>
    <b>5 a 9 anos:</b> %{customdata[6]}<br>
    <b>10 a 14 anos:</b> %{customdata[7]}<br>
    <b>15 a 19 anos:</b> %{customdata[8]}<br>
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
    return fig

def merge_setores_com_dados_demograficos(gdf, dados_demograficos):
    gdf = gdf.merge(
        dados_demograficos,
        left_on="CD_SETOR",
        right_on="CD_setor",
        how="left"
    )
    return gdf

def merge_escolas_com_matriculas(df_escola, df_matricula):
    df_escola = df_escola.merge(
        df_matricula.drop(columns=["NU_ANO_CENSO"]),
        on="CO_ENTIDADE",
        how="left"
    )
    return df_escola

def renomear_colunas_matriculas(df):
    """
    Renomeia as principais colunas de matrículas para nomes mais intuitivos.
    """

    mapa = {
        "QT_MAT_BAS": "MATRICULAS_EDUCACAO_BASICA",
        "QT_MAT_INF": "MATRICULAS_EDUCACAO_INFANTIL",
        "QT_MAT_FUND_AI": "MATRICULAS_FUNDAMENTAL_ANOS_INICIAIS",
        "QT_MAT_FUND_AF": "MATRICULAS_FUNDAMENTAL_ANOS_FINAIS",
        "QT_MAT_MED": "MATRICULAS_ENSINO_MEDIO",
        "QT_MAT_EJA": "MATRICULAS_EJA",
        "QT_MAT_PROF": "MATRICULAS_EDUCACAO_PROFISSIONAL",
    }

    return df.rename(columns=mapa)

def plotar_escolas(fig, df_escola: pd.DataFrame) -> None:
    
    pontos_escolas = px.scatter_map(
        df_escola,
        lat="LATITUDE",
        lon="LONGITUDE",
        color="REDE",
        #color_discrete_map={"Pública": "#2E8B57", "Privada": "#7B68EE",},
        #color_discrete_map={"Pública": "#009E73", "Privada": "#E69F00",},
        color_discrete_map={"Pública": "#2E7D32", "Privada": "#F57C00",},
        hover_name="NO_ENTIDADE",
        hover_data=[
            "CO_ENTIDADE",
            "NO_MUNICIPIO",
            "DEPENDENCIA",
            "SITUACAO_FUNCIONAMENTO",
            "MATRICULAS_EDUCACAO_BASICA",
            "MATRICULAS_EDUCACAO_INFANTIL",
            "MATRICULAS_FUNDAMENTAL_ANOS_INICIAIS",
            "MATRICULAS_FUNDAMENTAL_ANOS_FINAIS",
            "MATRICULAS_ENSINO_MEDIO",
            "MATRICULAS_EJA",
            "MATRICULAS_EDUCACAO_PROFISSIONAL"

        ],
        #zoom=8,
        #map_style="carto-positron"
    )

    pontos_escolas.update_traces(marker=dict(size=8))
    for trace in pontos_escolas.data:
        fig.add_trace(trace)
   
    return fig

