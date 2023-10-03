# Base image
FROM debian:bullseye

# Set environment variables to disable prompts
ENV DEBIAN_FRONTEND=noninteractive

# Create user with sudo only in the container for security.
RUN useradd docker && echo "docker:docker" | chpasswd && mkdir -p /home/docker && chown docker:docker /home/docker
RUN mkdir -p /mnt/data && chown -R docker:docker /mnt/data

RUN apt-get update && apt-get install -y sudo

RUN usermod -aG sudo docker

RUN echo "docker ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
# add write perms for user 'docker' in the correct dirs ( where it cant mess things up much. it does have passwordless sudo, so it can override this if it figures out it has sudo.)
RUN chown -R docker:docker /mnt/data

# Update package list and install essential utilities and runtimes
RUN sudo apt-get update && apt-get install -y \
    jq \
    build-essential \
    python3 \
    python3-pip \
    python3-dev \
    curl \
    libssl-dev \
    libexpat1 \
    r-base \
    r-base-dev

# install nodejs stuff
RUN sudo apt-get update
RUN sudo apt-get install -y ca-certificates curl gnupg
RUN sudo mkdir -p /etc/apt/keyrings
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
RUN NODE_MAJOR=20
RUN echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
RUN sudo apt-get update
RUN sudo apt-get install nodejs -y


# Copy unified requirements.txt into the image
COPY ./requirements.txt /tmp/

# Install Python packages
RUN awk '/\[python\]/, /^\s*$/' /tmp/requirements.txt | grep -v '^\[python\]' > /tmp/python_requirements.txt && \
    pip3 install --no-cache-dir -r /tmp/python_requirements.txt --no-input

# Create an initial empty package.json
RUN echo '{}' > /tmp/package.json

RUN awk '/\[node\]/, /^\s*$/' /tmp/requirements.txt | grep -v '^\[node\]' > /tmp/node_requirements.txt && \
    while read -r package; do \
        name=$(echo $package | grep -Eo "^[a-zA-Z0-9_-]+") && \
        version=$(echo $package | grep -Eo "[>=<]+[0-9.]+"); \
        if [ -z "$version" ]; then version="*"; fi && \
        jq ".dependencies.\"$name\" = \"$version\"" /tmp/package.json > /tmp/package_temp.json && mv /tmp/package_temp.json /tmp/package.json; \
    done < /tmp/node_requirements.txt



# Install NodeJS packages
RUN npm install --save --yes --no-package-lock --prefix /tmp

# Install R packages
RUN awk '/\[r\]/,/^\s*$/' /tmp/requirements.txt | grep -v '^\[r\]' > /tmp/r_requirements.txt && \
    while read -r package; do \
        R -e "install.packages('$package', repos='http://cran.rstudio.com/', dependencies=TRUE, INSTALL_opts = c('--no-tests'))"; \
    done < /tmp/r_requirements.txt

# Install NodeJS packages

# Remove temporary files
RUN rm /tmp/package.json /tmp/node_requirements.txt /tmp/python_requirements.txt /tmp/r_requirements.txt

# workdir set. pray it dosent try to go exploring.
WORKDIR /mnt/data
