CREATE TABLE public.ine_0009875 (
    nuts_i bpchar(64) NOT NULL,
    nuts_ii bpchar(64) NOT NULL,
    tipo_alojamento bpchar(64) NOT NULL,
    ano int4 NOT NULL,
    capacidade_alojamento float4 NULL,
    create_date date NULL,
    update_date date NULL,
    CONSTRAINT ine_0009875_pkey PRIMARY KEY (nuts_i, nuts_ii, tipo_alojamento, ano)
);
