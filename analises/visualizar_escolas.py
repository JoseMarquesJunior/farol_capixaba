import pandas as pd 
import time
import plotly.express as px
import numpy as np
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

NOME_ARQUIVO_ESCOLA = "analises/escolas_ES.xlsx"
NOME_ARQUIVO_MATRICULA = "educacao/data/extracted/2025/microdados_censo_escolar_2025/dados/Tabela_Matricula_2025.csv"

def mapear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    mapa_dependencia = {
        1: "Federal",
        2: "Estadual",
        3: "Municipal",
        4: "Privada"
    }

    mapa_situacao = {
        1: "Em atividade",
        2: "Paralisada",
        3: "Extinta (ano do Censo)",
        4: "Extinta em anos anteriores"
    }

    novas_colunas = pd.DataFrame({
        "REDE": np.where(
            df_escola["TP_DEPENDENCIA"] == 4,
            "Privada",
            "Pública"
        ),

        "DEPENDENCIA": df_escola["TP_DEPENDENCIA"].map(mapa_dependencia),

        "SITUACAO_FUNCIONAMENTO": df_escola["TP_SITUACAO_FUNCIONAMENTO"].map(mapa_situacao)
    })

    df = pd.concat([df, novas_colunas], axis=1)
    
    return df

def mostrar_coordenadas_duplicadas(df_escola):
    """
    Exibe as escolas que possuem exatamente a mesma latitude e longitude.
    """
    
    duplicadas = (
        df_escola
        .dropna(subset=["LATITUDE", "LONGITUDE"])
        .groupby(["LATITUDE", "LONGITUDE"])
        .filter(lambda x: len(x) > 1)
        .sort_values(["LATITUDE", "LONGITUDE"])
    )

    if duplicadas.empty:
        print("Nenhuma coordenada duplicada encontrada.")
        return duplicadas

    for (lat, lon), grupo in duplicadas.groupby(["LATITUDE", "LONGITUDE"]):
        print("=" * 80)
        print(f"Latitude : {lat}")
        print(f"Longitude: {lon}")
        print(f"Quantidade de escolas: {len(grupo)}/n")

        

        print(
            grupo[
                [
                    "CO_ENTIDADE",
                    "NO_ENTIDADE",
                    "NO_MUNICIPIO",
                    "DS_ENDERECO",
                    "NU_ENDERECO"
                ]
            ].to_string(index=False)
        )
        
        print()

    return duplicadas

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

def plotar_escolas(df_escola: pd.DataFrame) -> None:
    fig = px.scatter_map(
        df_escola,
        lat="LATITUDE",
        lon="LONGITUDE",
        color="REDE",
        color_discrete_map={
            "Pública": "#2E8B57",
            "Privada": "#7B68EE",
        },
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
        zoom=8,
        map_style="carto-positron"
    )
    fig.update_traces(
        marker=dict(size=8)
    )
    fig.show()
    return fig

df_escola = pd.read_excel(NOME_ARQUIVO_ESCOLA)
#df_escola = mapear_colunas(df_escola)

df_escola = df_escola[df_escola["TP_SITUACAO_FUNCIONAMENTO"] == 1]

df_matricula = pd.read_csv(NOME_ARQUIVO_MATRICULA, sep=";", encoding="latin1", low_memory=False)

df_escola = df_escola.merge(
    df_matricula.drop(columns=["NU_ANO_CENSO"]),
    on="CO_ENTIDADE",
    how="left"
)

print(df_escola.head())
df_escola = renomear_colunas_matriculas(df_escola)

df_escola.to_excel("analises/escolas_ES_ativas.xlsx", index=False)

fig = plotar_escolas(df_escola)
fig.write_html("analises/escolas_ES.html")