#!/bin/bash
find ../airflow_logs -mtime +30 -type f | while read file; do
    String="ERROR"
    if ! grep -q "$String" "$file" ; then
        echo "Deleted file: '$file'"
        rm "$file"
    else
        echo "'$file' have strig ERROR"
    fi
done
find ../airflow_logs -type d -empty -delete
