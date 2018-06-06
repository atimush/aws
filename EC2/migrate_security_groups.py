#!/usr/bin/env python

"""
Tool to migrate/synchronize AWS EC2 Security Groups between regions and VPCs.
Requirements:
1. AWS CLI tool;
2. Required credentials to EC2.

Supports:
1. One-to-one at a time Region/VPC processing
2. Rules for IPv4 and IPv6;
3. Tag with Key: Name and ALL Tags.

IMPORTANT: Might be incompatible with older versions of AWS CLI!
"""

import os, sys, subprocess, getopt, json

def getid_sg(region,vpc,gname):
    cmd = ['aws', 'ec2', 'describe-security-groups', '--region=%s' %region, '--filters', 'Name=vpc-id,Values=%s' %vpc, 'Name=group-name,Values=%s' %gname, '--query', 'SecurityGroups[*].{grid:GroupId}']
    get = subprocess.check_output(cmd)
    data = json.loads(get)
    if data:
        grid = data[0]['grid']
        return grid
    else:
        grid = None
        return grid

def migrate_policy(direction,family):
    if direction == 'IpPermissions':
        call = 'ingress'
    if direction == 'IpPermissionsEgress':
        call = 'egress'
    for rule in sg[direction]:
        for iipr in rule[family]:
            if '-1' in rule['IpProtocol']:
                ifp = 0
                itp = 65535
            else:
                ifp = rule['FromPort']
                itp = rule['ToPort']
            ipr = rule['IpProtocol']
            if 'Description' not in iipr:
                idesc = ' '
            else:
                idesc = iipr['Description']
            if family == 'IpRanges':
                icidr = iipr['CidrIp']
                cmd = "aws --region %s ec2 authorize-security-group-%s --group-id %s --ip-permissions '[{\"IpProtocol\": \"%s\", \"FromPort\": %s, \"ToPort\": %s, \"IpRanges\": [{\"CidrIp\": \"%s\", \"Description\": \"%s\"}]}]'" %(dregion,call,dgrid,ipr,ifp,itp,icidr,idesc)
            if family == 'Ipv6Ranges':
                icidr = iipr['CidrIpv6']
                cmd = "aws ec2 --region %s authorize-security-group-%s --group-id %s --ip-permissions '[{\"IpProtocol\": \"%s\", \"FromPort\": %s, \"ToPort\": %s, \"Ipv6Ranges\": [{\"CidrIpv6\": \"%s\", \"Description\": \"%s\"}]}]'" %(dregion,call,dgrid,ipr,ifp,itp,icidr,idesc)
            print "        ---> Migrating %s rule: %s --- %s:%s --- %s \"%s\"" %(call.upper(),ipr.upper(),ifp,itp,icidr,idesc)
            os.system(cmd)

def migrate_tags(selector):
    if 'Tags' in sg:
        stags = sg['Tags']
        for stag in stags:
            if selector == 'name':
                if 'Name' in stag['Key']:
                    tagkey = stag['Key']
                    tagvalue = stag['Value']
                    print "        ---> Migrating TAG Key:'%s' Value:'%s'" %(tagkey,tagvalue)
                    cmd = "aws ec2 create-tags --resources '%s' --tags Key=\"%s\",Value=\"%s\"" %(dgrid,tagkey,tagvalue)
                    os.system(cmd)
            elif selector == 'all':
                    tagkey = stag['Key']
                    tagvalue = stag['Value']
                    print "        ---> Migrating TAG Key:'%s' Value:'%s'" %(tagkey,tagvalue)
                    cmd = "aws ec2 create-tags --resources '%s' --tags Key=\"%s\",Value=\"%s\"" %(dgrid,tagkey,tagvalue)
                    os.system(cmd)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:", ["help", "sreg=", "dreg=", "svpc=", "dvpc=", "gnames=", "tags="])
        if len(sys.argv[1:]) < 5:
            print "ERROR: Mandatory arguments not supplied"
            usage()
            sys.exit(2)
    except getopt.GetoptError as err:
        print "ERROR: " + str(err)
        usage()
        sys.exit(2)
    sregion = None
    global dregion
    dregion = None
    svpc = None
    dvpc = None
    gnames = None
    tags = None

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            return
        elif o in ("-sr", "--sreg"):
            sregion = a
        elif o in ("-dr", "--dreg"):
            dregion = a
        elif o in ("-sv", "--svpc"):
            svpc = a
        elif o in ("-dv", "--dvpc"):
            dvpc = a
        elif o in ("-gn", "--gnames"):
            gnames = a
            gname_list = gnames.split(",")
        elif o in ("-t", "--tags"):
            tags = a

# Get Group ID and validate if exists in source Region/VPC
    for gname in gname_list:
        sgrid = getid_sg(sregion,svpc,gname)
        if sgrid != None:
            print "\n-------------- Processing %s Group --------------" %gname.upper()
            print "INFO: Group has been validated in source %s/%s" %(sregion.upper(),svpc.upper())
        else:
            print "ERROR: Unable to find the source group"
            sys.exit(2)

        cmd1 = ['aws', 'ec2', 'describe-security-groups', '--region=%s' %sregion, '--output=json', '--group-id=%s' % sgrid]
        get = subprocess.check_output(cmd1)
        data = json.loads(get)
        global sg,dgrid
        sg = data['SecurityGroups'][0]
        sdesc = sg['Description']
        sname = sg['GroupName']
        dgrid = getid_sg(dregion,dvpc,gname)

        if dgrid == None:
            print "INFO: Target group is missing in %s/%s. Creating it and migrating rules:" %(dregion.upper(),dvpc.upper())
            cmd2 = "aws ec2 create-security-group --group-name '%s' --description \"%s\" --vpc-id %s" %(sname,sdesc,dvpc)
            os.system(cmd2)
            dgrid = getid_sg(dregion,dvpc,gname)
        else:
            print "INFO: Target group is present in %s/%s.      \nMigrating rules only (duplicates might be expected):" %(dregion.upper(),dvpc.upper())

        migrate_policy('IpPermissions','IpRanges')
        migrate_policy('IpPermissions','Ipv6Ranges')
        migrate_policy('IpPermissionsEgress','IpRanges')
        migrate_policy('IpPermissionsEgress','Ipv6Ranges')
        if tags == 'name':
            migrate_tags('name')
        elif tags == 'all':
            migrate_tags('all')

def usage():
    print "EXAMPLE: migrate_security_groups.py --sreg=eu-west-2 --dreg=eu-west-1 --svpc=vpc-2f987446 --dvpc=vpc-a36511c7 --gnames='test1' --tags=name"
    print "EXAMPLE: migrate_security_groups.py --sreg=eu-west-2 --dreg=eu-west-1 --svpc=vpc-2f987446 --dvpc=vpc-a36511c7 --gnames='test1','test 2' --tags=all"
    print "     -h  --help          - Helper"
    print "     -sr --sreg          - Source region"
    print "     -dr --dreg          - Destination region"
    print "     -sv --svpc          - Source VPC ID"
    print "     -dv --dvpc          - Destination VPC ID"
    print "     -gn --gnames        - Security Group Name"
    print "     -t  --tags          - Optional: Tag options (Key:Name Only/ALL)"

if __name__ == "__main__":
    main()
