FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ENV PYTHONUNBUFFERED=1

# The base image ships an APT source for Yarn's old Debian repo, whose GPG key
# has expired. Left alone, it breaks the first `apt-get update` that runs —
# including the one inside Dev Container feature install scripts. Remove it.
RUN find /etc/apt/sources.list.d -maxdepth 1 -type f \( -name "*.list" -o -name "*.sources" \) \
    -exec sh -c 'grep -qi "dl.yarnpkg.com" "$1" && rm -f "$1"' _ {} \;

# [Optional] If your requirements rarely change, uncomment this section to add them to the image.
# COPY requirements.txt /tmp/pip-tmp/
# RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
#    && rm -rf /tmp/pip-tmp

# [Optional] Uncomment this section to install additional OS packages.
# RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#     && apt-get -y install --no-install-recommends <your-package-list-here>