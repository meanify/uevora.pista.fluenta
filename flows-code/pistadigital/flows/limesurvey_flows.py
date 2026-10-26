import io
import re
import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter
import pandas as pd

from pistadigital.mappings.mappings import survey_mappings
from pistadigital.utils.strip_html import strip_html
from pistadigital.utils.database import get_engine

from citric import Client
from citric.exceptions import LimeSurveyStatusError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("pista.fluenta")
logger.setLevel(logging.INFO)

def obter_mapeamento(survey_id):
    mapping = survey_mappings.get(str(survey_id))
    if mapping is None:
        raise ValueError(f"No mapping configured for survey {survey_id}.")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", mapping["table_name"]):
        raise ValueError(f"Invalid table name configured for survey {survey_id}.")
    return mapping


def limesurvey_client():
    names = ("LIME_SURVEY_URL", "LIME_SURVEY_USERNAME", "LIME_SURVEY_PASSWORD")
    settings = {name: os.getenv(name, "") for name in names}
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise RuntimeError("Missing LimeSurvey settings: " + ", ".join(missing))
    return Client(*(settings[name] for name in names))


def get_export_end_id(survey_id, from_response_id):
    """Snapshot the last available response ID without downloading full answers."""
    logger.info(
        "Survey %s: discovering last response ID from ID %s.",
        survey_id, from_response_id,
    )
    with limesurvey_client() as client:
        content = client.export_responses(
            survey_id, file_format="csv", heading_type="code",
            from_response_id=from_response_id, fields=["id"],
        )
    if content in (b"", b"\r\n"):
        logger.info("Survey %s: no response IDs returned.", survey_id)
        return None
    ids = pd.read_csv(io.BytesIO(content), delimiter=";", usecols=["id"],
                      dtype={"id": "int64"})
    if ids.empty:
        logger.info("Survey %s: no response IDs returned.", survey_id)
        return None
    if ids["id"].lt(from_response_id).any():
        raise ValueError(f"Survey {survey_id} returned response IDs before the requested start.")
    last_id = int(ids["id"].max())
    logger.info("Survey %s: last response ID is %d.", survey_id, last_id)
    return last_id


def get_last_answer_id(survey_id: int) -> int:
    """
    Docstring for test
    """
    mappings = obter_mapeamento(survey_id)
    engine = get_engine()
    # perform query to get last answer ID
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT MAX(id) FROM {mappings.get('table_name')}"))
            last_id = result.scalar()
            next_id = int(last_id) + 1 if last_id is not None else 1
            logger.info("Next response ID for survey %s is %s", survey_id, next_id)
            return next_id
    except SQLAlchemyError as e:
        raise RuntimeError(
            f"Could not determine the next response ID for survey {survey_id}."
        ) from e
    finally:
        engine.dispose()


PARTICIPANT_PAGE_SIZE = 1000


def fetch_participants(client, survey_id) -> list:
    """Retrieve every participant for a survey.

    ``list_participants`` returns at most ``limit`` rows per call, so a single
    request silently truncates surveys with more participants than the page
    size. Page until a short page comes back.
    """
    records: list = []
    start = 0
    while True:
        try:
            batch = client.list_participants(
                survey_id, start=start, limit=PARTICIPANT_PAGE_SIZE,
                attributes=["id", "firstname", "lastname", "email"],
            )
        except LimeSurveyStatusError:
            # LimeSurvey reports an exhausted range as a status error rather
            # than an empty list. On the first page that still means the survey
            # has no participants at all, which stays an error as before.
            if start == 0:
                raise
            break
        if not batch:
            break
        records.extend(batch)
        if len(batch) < PARTICIPANT_PAGE_SIZE:
            break
        start += len(batch)
    logger.info("Survey %s: retrieved %d participants.", survey_id, len(records))
    return records


def no_participants(
    survey_id: int,
    from_response_id: int = None,
    increment: int | None = 1000,
) -> pd.DataFrame:
    """
    Docstring for test
    """

    with limesurvey_client() as client:

        if from_response_id is None:
            from_response_id = get_last_answer_id(survey_id)
        to_response_id = (
            from_response_id + increment if increment is not None else None
        )

        logger.info("Exporting answers for survey %s from response ID %s to %s", survey_id, from_response_id, to_response_id)

        additional_options = {'stripHtmlCode': 1}
        content = client.export_responses(survey_id, file_format="csv", heading_type="code", response_type="long",
                                          from_response_id=from_response_id, to_response_id=to_response_id,
                                          additional_options=additional_options)
       
        if content != b'\r\n' and content != b'':
            answers = pd.read_csv(
                io.BytesIO(content), delimiter=";", low_memory=False,
                parse_dates=survey_mappings[str(survey_id)]["date_fields"],
            )
            answers = answers[~answers['submitdate'].isnull()]

            answers = strip_html(answers)
        
            for col in survey_mappings[str(survey_id)]["drop_columns"]:
                if col in answers.columns:
                    answers.drop(columns = [col], inplace=True)

            return answers
            
        else:
            logger.warning("Export is empty for the given response ID range.")

    return pd.DataFrame()

def participants(
    survey_id: int,
    from_response_id: int = None,
    increment: int | None = 1000,
) -> pd.DataFrame:
    """
    Docstring for test
    """
    with limesurvey_client() as client:

        if from_response_id is None:
            from_response_id = get_last_answer_id(survey_id)
        to_response_id = (
            from_response_id + increment if increment is not None else None
        )

        logger.info("Exporting answers for survey %s from response ID %s to %s", survey_id, from_response_id, to_response_id)

        additional_options = {'stripHtmlCode': 1}
        content = client.export_responses(survey_id, file_format="csv", heading_type="code", response_type="long",
                                          from_response_id=from_response_id, to_response_id=to_response_id,
                                          additional_options=additional_options)
        
        if content != b'\r\n' and content != b'':
            answers = pd.read_csv(
                io.BytesIO(content), delimiter=";", low_memory=False,
                parse_dates=survey_mappings[str(survey_id)]["date_fields"],
            )
            answers = answers[~answers['submitdate'].isnull()]

            answers = strip_html(answers)

            # Merge participant info
            sv_parties = pd.DataFrame(fetch_participants(client, survey_id))
            sv_parties.drop(columns = ["tid"], inplace=True)
            sv_parties = pd.json_normalize(sv_parties.to_dict(orient='records'))
            # Rename columns to remove "participant_info."" prefix
            sv_parties.rename(columns=lambda x: re.sub(r'^participant_info\.', '', x), inplace=True)

            for col in survey_mappings[str(survey_id)]["drop_columns"]:
                if col in answers.columns:
                    answers.drop(columns = [col], inplace=True)

            answers = answers.merge(sv_parties, left_on="token", right_on="token", how="left")
            return answers
            
        else:
            logger.warning("Export is empty for the given response ID range.")

    return pd.DataFrame()

def export_answers(
    survey_id: int,
    from_response_id: int = None,
    increment: int = 1000,
    to_response_id: int = None,
) -> str | None:
    """Export mapped responses without requiring a database connection."""
    answers = processar_inquerito(
        survey_id,
        from_response_id,
        increment,
        exportar_csv=True,
        to_response_id=to_response_id,
    )
    return str(csv_path(survey_id, answers)) if not answers.empty else None

def load_answers(survey_id: int, file_path: str) -> str:
    """Append responses from an existing semicolon-delimited CSV."""

    answers = pd.read_csv(file_path, delimiter=';')
    write_answers(survey_id, answers)
    return f"Successfully loaded {len(answers)} answers into table: {obter_mapeamento(survey_id)['table_name']}"


def export_and_load(
    survey_id: int,
    from_response_id: int,
    increment: int,
    to_response_id: int = None,
) -> str | None:
    """Export one interval and load it, preserving the Airflow batch behavior."""
    if from_response_id is None:
        from_response_id = get_last_answer_id(survey_id)
    if to_response_id is None:
        to_response_id = from_response_id + increment
    answers = processar_inquerito(
        survey_id,
        from_response_id,
        increment,
        exportar_csv=True,
        gravar_bd=True,
        to_response_id=to_response_id,
    )
    if answers.empty:
        return None
    return f"Successfully loaded {len(answers)} answers for survey {survey_id}"


def csv_path(survey_id, answers, directory=None):
    directory = Path(
        directory if directory is not None
        else os.getenv("PISTAFLOWS_EXPORTS_PATH") or "."
    )
    return directory / f"{survey_id}_answers_{answers['id'].min()}-{answers['id'].max()}.csv"


def write_answers(survey_id, answers):
    """Append mapped responses in one transaction without an intermediate CSV."""
    mapping = obter_mapeamento(survey_id)
    if answers.empty:
        logger.warning("No responses to write for survey %s.", survey_id)
        return
    engine = get_engine()
    try:
        with engine.begin() as connection:
            answers.to_sql(mapping["table_name"], con=connection, index=False,
                           if_exists="append")
    except (SQLAlchemyError, pd.errors.DatabaseError) as exc:
        raise RuntimeError(
            f"Could not append responses for survey {survey_id}; transaction rolled back."
        ) from exc
    finally:
        engine.dispose()


def processar_inquerito(
    survey_id,
    from_response_id=None,
    increment=1000,
    exportar_csv=True,
    gravar_bd=False,
    caminho_csv=None,
    to_response_id=None,
    output_directory=None,
):
    """Fetch successive response-ID intervals, then write selected outputs."""
    mapping = obter_mapeamento(survey_id)
    if caminho_csv is not None and not exportar_csv:
        raise ValueError("caminho_csv requires exportar_csv=True.")
    if output_directory is not None and caminho_csv is not None:
        raise ValueError("output_directory cannot be used with caminho_csv.")
    if isinstance(increment, bool) or not isinstance(increment, int) or increment < 1:
        raise ValueError("increment must be a positive integer.")
    if from_response_id is not None and (
        isinstance(from_response_id, bool)
        or not isinstance(from_response_id, int) or from_response_id < 1
    ):
        raise ValueError("from_response_id must be a positive integer.")
    if to_response_id is not None and (
        isinstance(to_response_id, bool)
        or not isinstance(to_response_id, int) or to_response_id < 1
    ):
        raise ValueError("to_response_id must be a positive integer.")
    if from_response_id is None:
        from_response_id = get_last_answer_id(survey_id) if gravar_bd else 1
    if to_response_id is not None and to_response_id < from_response_id:
        raise ValueError("to_response_id must be greater than or equal to from_response_id.")

    fetch = participants if mapping["has_participants"] else no_participants
    if to_response_id is None:
        to_response_id = get_export_end_id(str(survey_id), from_response_id)
        if to_response_id is None:
            logger.warning("No completed responses for survey %s.", survey_id)
            return pd.DataFrame()
    batches = []
    batch_start = from_response_id
    batch_number = 0
    total_records = 0
    total_batches = (to_response_id - from_response_id) // (increment + 1) + 1
    while True:
        batch_increment = min(increment, to_response_id - batch_start)
        batch_end = batch_start + batch_increment
        batch_number += 1
        logger.info(
            "Survey %s: starting batch %d/%d, response IDs %d-%d.",
            survey_id, batch_number, total_batches, batch_start, batch_end,
        )
        started = perf_counter()
        batch = fetch(str(survey_id), batch_start, batch_increment)
        total_records += len(batch)
        logger.info(
            "Survey %s: completed batch %d/%d, response IDs %d-%d: "
            "%d completed responses, %d cumulative, %.2f seconds.",
            survey_id, batch_number, total_batches, batch_start, batch_end,
            len(batch), total_records, perf_counter() - started,
        )
        if not batch.empty:
            batches.append(batch)
        if batch_end >= to_response_id:
            break
        batch_start = batch_end + 1
    logger.info(
        "Survey %s: combining %d non-empty batches (%d completed responses).",
        survey_id, len(batches), total_records,
    )
    answers = pd.concat(batches, ignore_index=True) if batches else pd.DataFrame()
    if answers.empty:
        logger.warning("No completed responses for survey %s.", survey_id)
        return answers
    logger.info("Survey %s: transforming %d completed responses.", survey_id, len(answers))
    answers = answers.copy()
    now = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
    answers["create_date"] = now
    answers["update_date"] = now
    answers = answers.rename(columns=mapping["columns"])
    if gravar_bd:
        logger.info(
            "Survey %s: writing %d responses to database table %s.",
            survey_id, len(answers), mapping["table_name"],
        )
        write_answers(survey_id, answers)
        logger.info("Survey %s: database write completed.", survey_id)
    if exportar_csv:
        filename = (
            Path(caminho_csv)
            if caminho_csv is not None
            else csv_path(survey_id, answers, output_directory)
        )
        logger.info(
            "Survey %s: writing %d responses to CSV %s.",
            survey_id, len(answers), filename,
        )
        answers.to_csv(filename, sep=";", quotechar='"', quoting=csv.QUOTE_MINIMAL,
                       index=False, encoding="utf-8")
        logger.info("Exported answers to %s", filename)
    return answers