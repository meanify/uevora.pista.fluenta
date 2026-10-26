# Deploy in Kubernetes

kubectl get ns fluenta || kubectl create ns fluenta

## Credentials

Credentials are **not** stored in these manifests. Every component reads them
from a single `Secret` named `airflow-secrets`, declared at the top of
[0_secrets_and_volumes.yaml](0_secrets_and_volumes.yaml) with **placeholder**
values:

| Key                 | Used by                                                     |
| ------------------- | ----------------------------------------------------------- |
| `postgres-password` | `2_airflow_postgres.yaml` (database init), and the Airflow DSNs in `4_airflow_dbmigration.yaml` / `5_airflow_airflow.yaml` |
| `fernet-key`        | `AIRFLOW__CORE__FERNET_KEY` in `4_airflow_dbmigration.yaml` / `5_airflow_airflow.yaml` |

The DSNs reference the password through Kubernetes dependent-variable
expansion, e.g.

    postgresql://airflow:$(POSTGRES_PASSWORD)@airflow-postgres/airflow

For this to expand, `POSTGRES_PASSWORD` must stay the **first** entry in that
container's `env:` list. If it is removed or reordered after the DSN, the
literal string `$(POSTGRES_PASSWORD)` is passed through and the connection
fails.

### Applying

`0_secrets_and_volumes.yaml` contains placeholders, so applying the whole file
**overwrites the live Secret and breaks the deployment**. Create the Secret
separately with the real values:

    kubectl -n fluenta create secret generic airflow-secrets \
      --from-literal=postgres-password='<password>' \
      --from-literal=fernet-key="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

To change one value in place:

    kubectl -n fluenta patch secret airflow-secrets \
      -p '{"stringData":{"postgres-password":"<new password>"}}'

### Rotation

Both previous values were committed to this repository and remain in git
history, so they must be treated as public and rotated.

- **`postgres-password`** — the database was initialised with the old password,
  so changing the Secret alone is not enough. Change the role first, then the
  Secret, then restart the Airflow pods:

      kubectl -n fluenta exec deploy/airflow-postgres -- \
        psql -U airflow -c "ALTER ROLE airflow WITH PASSWORD '<new password>';"

- **`fernet-key`** — this key decrypts every password stored in an Airflow
  Connection or Variable. Rotating it **invalidates all of them**, so either
  re-enter each Connection afterwards, or set `AIRFLOW__CORE__FERNET_KEY` to
  `<new key>,<old key>` (new first) so Airflow can re-encrypt existing values
  before the old key is dropped. Affected connections include `pista_db` and
  `limesurvey`.
