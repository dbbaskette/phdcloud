# Copyright (C) 2013-2014 Pivotal Software, Inc.
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the under the Apache License,
# Version 2.0 (the "License”); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM dcloud/dns-base:0.2

RUN echo root:changeme | chpasswd

RUN yum -y install httpd wget tar

RUN yum -y install openssh-server openssh-clients tar

# Install JDK on ALL Nodes
RUN wget --no-cookies --no-check-certificate --header "Cookie: oraclelicense=accept-securebackup-cookie" "http://download.oracle.com/otn-pub/java/jdk/7u67-b01/jdk-7u67-linux-x64.rpm" -O /tmp/jdk-7-linux-x64.rpm
RUN rpm -ivh /tmp/jdk-7-linux-x64.rpm

 
# Create Key for Passwordless SSH Sharing

RUN ssh-keygen -t rsa -N "" -f /root/.ssh/id_rsa
RUN echo 'StrictHostKeyChecking no' > /root/.ssh/config
RUN useradd -m gpadmin
RUN echo gpadmin:changeme | chpasswd
RUN su gpadmin -c "ssh-keygen -t rsa -N '' -f /home/gpadmin/.ssh/id_rsa"
RUN su gpadmin -c "echo 'StrictHostKeyChecking no' > /home/gpadmin/.ssh/config"


# Install Prereqs

RUN yum -y install mod_ssl compat-readline5 createrepo sigar sudo selinux-policy rpm-cron ntp

# Setup for PHD

RUN yum -y install openssl nc postgresql-devel massh ed

#Disable Defaults requiretty in sudoers file
RUN  sed -i "s/Defaults    requiretty.*/ #Defaults    requiretty/g" /etc/sudoers

# FIXES FOR PHD INSTALL (HACKS)
# RedHat 6.5 Fix
# NO LONGER NEEDED WITH PHD2.1 RUN sed -i "s/6.5/6.4/" /etc/redhat-release
# iptables fix
RUN echo "echo not running." > /etc/init.d/iptables
# disable selinux
RUN sed -i "s/enforcing/disabled/" /etc/selinux/config
# Fix Hostname Resolution
##   EDIT   RUN fqdn = “$(/bin/hostname -f)”
##          RUN sed -i 's/^HOSTNAME=*/HOSTNAME=/‘ /filename