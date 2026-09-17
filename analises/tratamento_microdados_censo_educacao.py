import pandas as pd 
import time
import plotly.express as px
import numpy as np
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

NOME_ARQUIVO_ESCOLA = "educacao/data/extracted/2025/microdados_censo_escolar_2025/dados/Tabela_Escola_2025.csv"

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
            "SITUACAO_FUNCIONAMENTO"
        ],
        zoom=8,
        map_style="carto-positron"
    )
    fig.update_traces(
        marker=dict(size=8)
    )
    fig.show()
    return fig

def preencher_latitude_longitude(df, delay=1.1):
    """
    Preenche LATITUDE e LONGITUDE utilizando o endereço da escola.

    Estratégias:
        1) Rua + Número + Bairro + Município + UF + CEP
        2) Rua + Bairro + Município + UF
        3) Rua + Município + UF
        4) Bairro + Município + UF
        5) CEP
        6) Município + UF

    Retorna uma cópia do DataFrame.
    """

    df = df.copy()

    geolocator = Nominatim(user_agent="censo_escolar")

    for idx, row in df.iterrows():

        # Já possui coordenadas
        if (
            pd.notna(row["LATITUDE"])
            and pd.notna(row["LONGITUDE"])
        ):
            continue

        rua = str(row.get("DS_ENDERECO", "")).strip()
        numero = str(row.get("NU_ENDERECO", "")).strip()
        bairro = str(row.get("NO_BAIRRO", "")).strip()
        municipio = str(row.get("NO_MUNICIPIO", "")).strip()
        uf = str(row.get("SG_UF", "")).strip()
        cep = str(row.get("CO_CEP", "")).strip()

        # Limpeza
        numero = numero.upper()

        if numero in ["S/N", "SN", "S/Nº", "S N", "NAN", "NONE"]:
            numero = ""

        if bairro.upper().startswith("AREA RURAL"):
            bairro = ""

        if cep.lower() == "nan":
            cep = ""

        consultas = []

        # 1
        consultas.append(", ".join(
            x for x in [
                rua,
                numero,
                bairro,
                municipio,
                uf,
                f"CEP {cep}" if cep else "",
                "Brasil"
            ] if x
        ))

        # 2
        consultas.append(", ".join(
            x for x in [
                rua,
                bairro,
                municipio,
                uf,
                "Brasil"
            ] if x
        ))

        # 3
        consultas.append(", ".join(
            x for x in [
                rua,
                municipio,
                uf,
                "Brasil"
            ] if x
        ))

        # 4
        consultas.append(", ".join(
            x for x in [
                bairro,
                municipio,
                uf,
                "Brasil"
            ] if x
        ))

        # 5
        if cep:
            consultas.append(f"{cep}, Brasil")

        # 6
        consultas.append(f"{municipio}, {uf}, Brasil")

        encontrado = False

        for tentativa, endereco in enumerate(consultas, start=1):

            try:

                local = geolocator.geocode(endereco)

                if local:

                    df.at[idx, "LATITUDE"] = local.latitude
                    df.at[idx, "LONGITUDE"] = local.longitude

                    print(
                        f"✓ [{tentativa}] "
                        f"{row['NO_ENTIDADE']} -> "
                        f"{local.latitude:.6f}, {local.longitude:.6f}"
                    )

                    encontrado = True
                    break

            except (GeocoderTimedOut, GeocoderServiceError):
                pass

            time.sleep(delay)

        if not encontrado:

            print(f"✗ Não encontrado: {row['NO_ENTIDADE']}")

    return df

df_escola = pd.read_csv(NOME_ARQUIVO_ESCOLA, sep=";", encoding="cp1252")
df_escola = df_escola[df_escola["NO_UF"] == "Espírito Santo"]

df_escola = mapear_colunas(df_escola)
df_escola = preencher_latitude_longitude(df_escola)
df_escola.to_excel("analises/escolas_ES.xlsx", index=False)
fig = plotar_escolas(df_escola)
fig.write_html("analises/escolas_ES.html")