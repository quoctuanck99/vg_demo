ARG BASE_IMAGE='python:3.11-slim'
FROM $BASE_IMAGE AS base

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /opt/app/
RUN mkdir -p media
RUN chmod -R 777 media

FROM base as dependencies
RUN apt-get update && apt-get install gcc -y && apt-get install ffmpeg -y && apt-get install build-essential -y\
    && apt-get install libssl-dev -y \
    && apt-get install ca-certificates -y \
    && apt-get install libasound2 -y  \
    && apt-get install wget -y \
    && wget -O - https://www.openssl.org/source/old/1.1.1/openssl-1.1.1u.tar.gz | tar zxf - \
    && cd openssl-1.1.1u \
    && ./config --prefix=/usr/local \
    && make -j $(nproc) \
    && make install_sw install_ssldirs \
    && ldconfig -v


FROM dependencies as pip_packages
COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM pip_packages as sources
COPY ./ ./

FROM sources as cleaning
RUN rm -rf /var/lib/apt/lists/*
