#!/bin/bash

function disable_ipv6() {
    # Speed up updating.. See following link for details.
    # http://askubuntu.com/questions/272796/connecting-to-archive-ubuntu-com-takes-too-long

    sudo sysctl "net.ipv6.conf.all.disable_ipv6=1"     > /dev/null
    sudo sysctl "net.ipv6.conf.default.disable_ipv6=1" > /dev/null
    sudo sysctl "net.ipv6.conf.lo.disable_ipv6=1"      > /dev/null

    if grep -q 'net.ipv6.conf.all.disable_ipv6' /etc/sysctl.conf; then
        echo "IPv6 already disabled"
    else
        echo "Disabling IPv6 for better speed"

        echo "#disable ipv6"                          | sudo tee -a /etc/sysctl.conf
        echo "net.ipv6.conf.all.disable_ipv6 = 1"     | sudo tee -a /etc/sysctl.conf
        echo "net.ipv6.conf.default.disable_ipv6 = 1" | sudo tee -a /etc/sysctl.conf
        echo "net.ipv6.conf.lo.disable_ipv6 = 1"      | sudo tee -a /etc/sysctl.conf
    fi
}

function install_packages() {

    # Load pre-defined settings, so debconf / apt-get won't ask any questions
    debconf-set-selections < /vagrant/tools/vagrant/debconf-set-selections.txt

    echo "Installing packages..."
    apt-get update
    apt-get -q -y install postgresql phppgadmin python python-virtualenv \
                          postgresql-server-dev-all python-psycopg2 lsof \
                          postgresql-contrib ssl-cert python-dev openssl \
                          libcurl4-openssl-dev libapache2-mod-wsgi
}

function install_requirements() {
    pip install -r /vagrant/requirements.txt
}

function setup_postgres() {
    # Make postgresql listen on external network interface. This helps for administering the DB with other tools
    find /etc/postgresql -name postgresql.conf | xargs -r sed -i "s/#\s*listen_addresses.*/listen_addresses = '*'/"
    pg_hba=`find /etc/postgresql -name pg_hba.conf`

    if [ -f $pg_hba ]; then
        echo "host all all 192.168.0.0/16 md5" >> $pg_hba
    else
        echo "pg_hba.conf not found. Is Postgresql installed properly?" > /dev/stderr
        exit 1
    fi
}

function enable_services() {
    update-rc.d postgresql enable default
    /etc/init.d/postgresql restart
}

function prepare_database() {
    # This empties any existing DB and re-creates it
    su - postgres -c psql < /vagrant/tools/vagrant/database.sql
}

function prepare_django() {
    # Now run all DB migrations for all installed apps
    su vagrant -c "cd /vagrant/app; python manage.py syncdb --noinput"
    cp -R /usr/local/lib/python2.7/dist-packages/django_browserid/static/browserid/ /vagrant/app/static/
    cp -R /usr/local/lib/python2.7/dist-packages/django/contrib/admin/static/admin/ /vagrant/app/static/
}

function configure_apache() {
    echo "Setting up Apache config..."
    cp /vagrant/tools/vagrant/vhost.conf /etc/apache2/sites-available/default
    cp /vagrant/tools/vagrant/phppgadmin.conf /etc/apache2/conf.d/phppgadmin
    usermod -a -G vagrant www-data
    a2enmod ssl
    a2enmod rewrite
    /etc/init.d/apache2 restart
}

function enable_cronjob() {
    # Set cronjobs
    crontab /vagrant/tools/vagrant/crontab
}

# vim:sw=4:ts=4:et:
