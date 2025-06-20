from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

app = FastAPI()

class QueryParams(BaseModel):
    client: int
    avaliationid: int
    
def query_relation(client, avaliationid, scale_id):
    query = """
    SELECT * FROM avaliations
    WHERE client_fk = :client AND id = :avaliationid AND scale_fk = :scale_id;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {'client': client, 'avaliationid': avaliationid, 'scale_id': scale_id})
        return pd.DataFrame(result.fetchall(), columns=result.keys())

def fetch_evaluation_details(avaliation_id, client, scale_id):
    query = """
    SELECT
        avaliations.id AS avaliationid,
        avaliations.client_fk,
        questions.id AS questionid,
        itens.score,
        avaliations.created_at AS timestamp
    FROM avaliations
    INNER JOIN answers ON avaliations.id = answers.avaliation_fk
    INNER JOIN itens ON itens.id = answers.item_fk
    INNER JOIN questions ON questions.id = answers.question_fk
    WHERE avaliations.id > :avaliation_id
      AND avaliations.client_fk = :client
      AND questions.scale_fk = :scale_id;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {'avaliation_id': avaliation_id, 'client': client, 'scale_id': scale_id})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def fetch_questions(scale_id):
    query = """
    SELECT id AS questionid, item_order, content, domain, color
    FROM questions
    WHERE scale_fk = :scale_id;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {'scale_id': scale_id})
        return pd.DataFrame(result.fetchall(), columns=result.keys())


def fetch_answers(client, avaliationid, scale_id):
    query = """
    WITH answers_cte AS (
        SELECT
            avaliations.id AS avaliationid,
            avaliations.client_fk,
            questions.id AS questionid,
            itens.score,
            avaliations.created_at AS timestamp
        FROM avaliations
        INNER JOIN answers ON avaliations.id = answers.avaliation_fk
        INNER JOIN itens ON itens.id = answers.item_fk
        INNER JOIN questions ON questions.id = answers.question_fk
        WHERE questions.scale_fk = :scale_id
    )
    SELECT * FROM answers_cte
    WHERE client_fk != :client OR avaliationid = :avaliationid;
    """
    params = {'client': client, 'avaliationid': avaliationid, 'scale_id': scale_id}
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        return pd.DataFrame(result.fetchall(), columns=result.keys())


@app.get("/recommend")
async def recommend_questions_route(avaliation: int, client: str, scale: int):
    avaliationid = avaliation

    # Verifica se a avaliação existe e pertence ao cliente e escala
    avaliation = query_relation(client, avaliationid, scale)
    if avaliation.empty:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    df_primary_answers = fetch_answers(client=client, avaliationid=avaliationid, scale_id=scale)
    df_questions = fetch_questions(scale_id=scale)

    pivot_table = df_primary_answers.pivot_table(index='avaliationid', columns='questionid', values='score', fill_value=0)
    matrix = pivot_table.values
    similarity_matrix = cosine_similarity(matrix)
    similarity_df = pd.DataFrame(similarity_matrix, index=pivot_table.index, columns=pivot_table.index)

    similarity_scores = similarity_df.loc[avaliationid]
    top_similarities = similarity_scores.sort_values(ascending=False).head(5)
    top_similarities = top_similarities.drop(avaliationid, errors='ignore')
    similar_ids = top_similarities.index.tolist()

    clients_df = df_primary_answers[['avaliationid', 'client_fk']].drop_duplicates()
    clients_df = clients_df.set_index('avaliationid')
    similar_clients = clients_df.loc[similar_ids]

    results_list = []
    for similar_client in similar_clients.itertuples():
        evaluation_details = fetch_evaluation_details(similar_client.Index, similar_client.client_fk, scale)
        if not evaluation_details.empty:
            results_list.append(evaluation_details)

    if results_list:
        combined_results = pd.concat(results_list, ignore_index=True)
        pivot_table_2 = combined_results.pivot_table(index='avaliationid', columns='questionid', values='score', fill_value=0)
        mean_scores = pivot_table_2.mean()
        evaluation_of_interest = df_primary_answers[df_primary_answers['avaliationid'] == avaliationid]
        pivot_avaliation_of_interest = evaluation_of_interest.pivot_table(index='avaliationid', columns='questionid', values='score', fill_value=0)
        evaluation_series = pivot_avaliation_of_interest.loc[avaliationid].squeeze()
        differences = mean_scores - evaluation_series
        filtered_differences = differences[differences < 0]
        sorted_filtered_differences = filtered_differences.sort_values(ascending=True)
        filtered_questions = df_questions[df_questions['questionid'].isin(sorted_filtered_differences.index)]
        # Ensure 'color' is included in the returned fields
        return {"filtered_questions": filtered_questions[['questionid', 'item_order', 'content', 'domain', 'color']].to_dict(orient='records')}
    else:
        return {"message": "Nenhum dado retornado para as avaliações similares."}
