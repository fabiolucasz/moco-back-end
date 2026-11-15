data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  owners = ["099720109477"] # Canonical
}

resource "aws_instance" "finpilot" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.allow_ssh_http.id]
  user_data_replace_on_change = true

  tags = {
    Name    = "finpilot-ec2"
    Project = "finpilot"
  }

  user_data_base64 = base64encode(replace(<<-EOF
#!/bin/bash
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1
echo "Starting Cloud-Init setup for FinPilot..."

# 1. Atualizar pacotes do sistema e instalar dependências
apt-get update -y
apt-get install -y docker.io git

# 2. Iniciar, habilitar o serviço Docker e adicionar o usuário ubuntu ao grupo docker
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu

# 3. Clonar o repositório do GitHub na pasta /app
if [ -d "/app" ]; then
  cd /app
  git pull origin main
else
  git clone https://github.com/fabiolucasz/moco-back-end.git /app
  chown -R ubuntu:ubuntu /app
fi

# 4. Entrar na pasta do projeto e criar o arquivo .env
cd /app
cat <<ENVEOF > .env
DATABASE_URL=${var.database_url}
SCHEME=${var.scheme}
USER=${var.db_user}
PASSWORD=${var.db_password}
HOST=${var.db_host}
PORT=${var.db_port}
DATABASE_NAME=${var.database_name}
SECRET_KEY=${var.secret_key}
ALGORITHM=${var.algorithm}
ACCESS_TOKEN_EXPIRE_MINUTES=${var.access_token_expire_minutes}
REFRESH_TOKEN_EXPIRE_DAYS=${var.refresh_token_expire_days}
DOMAIN=${var.domain}
ENVIRONMENT=${var.environment}
REDIS_URL=${var.redis_url}
GOOGLE_CLIENT_ID=${var.google_client_id}
GOOGLE_CLIENT_SECRET=${var.google_client_secret}
ENVEOF

# 5. Construir a imagem Docker e rodar o container na porta 8000
docker build -t finpilot .
docker rm -f finpilot-container || true
docker run -d --name finpilot-container --restart always --env-file .env -p 8000:8000 finpilot

echo "FinPilot deployment completed successfully!"
EOF
  , "\r\n", "\n"))
}
