"""
Tool to perform automatic snapshots of AWS EBS volumes defined by a retention policy.
Requirements:
1. AWS user and ID with required access to EC2;
2. Lambda and CloudWatch services.

Supports:
1. Multiple Regions.
2. EBS volume selection by adding Tag with Key: Backup and Value: Yes
3. Per volume retention policies (in days) defined by Tag with Key: BackupRetention and Value: $number_of_days

IMPORTANT:
1. Volumes marked for backup with 'Backup':'Yes' and without 'BackupRetention' tag
will not be automatically deleted!
2. region and account_id Lists are mandatory and must be supplied/adjuted manually.
"""

__author__ = 'Andrei Timus'

import boto3
import datetime


def lambda_handler(event, context):
    # Specify regions and Owner ID
    regions = ["eu-central-1", "eu-west-1"]
    account_id = ["104209064503"]

    # Iterate regions
    for region in regions:
        print "INFO: Processing region %s " % region
        ec2 = boto3.client('ec2', region_name=region)

        # Get the list of volumes marked for Backup
        volumes = ec2.describe_volumes(Filters=[{'Name': 'tag-key', 'Values': ['Backup', 'Yes']}])

        # Iterate volumes
        for volume in volumes['Volumes']:
            print "INFO: Backing up %s in %s" % (volume['VolumeId'], volume['AvailabilityZone'])

            # Create snapshot
            volumes = ec2.create_snapshot(VolumeId=volume['VolumeId'],
                                          Description='Created by Lambda backup function ebs-snapshot')

            # Get snapshot resource. Migrate Key:Name tag and process custom retention tags
            ec2resource = boto3.resource('ec2', region_name=region)
            snapshot = ec2resource.Snapshot(volumes['SnapshotId'])

            # Iterate tags
            if 'Tags' in volume:
                for tags in volume['Tags']:
                    if tags["Key"] == 'Name':
                        volumename = 'N/A'
                        volumename = tags["Value"]
                        snapshot.create_tags(Tags=[{'Key': 'Name', 'Value': volumename}])
                    if tags["Key"] == 'BackupRetention':
                        retention_days = None
                        retention_days = int(tags["Value"])
                        if retention_days != None:
                            delete_date = datetime.date.today() + datetime.timedelta(days=retention_days)
                            delete_fmt = delete_date.strftime('%Y-%m-%d')
                            snapshot.create_tags(Tags=[{'Key': 'DeleteOn', 'Value': delete_fmt}])
                        else:
                            print "INFO: No retention period set for volume %s." % (volume['VolumeId'])

        # Iterate Snapshots and Remove the old ones
        filter = [{'Name': 'tag-key', 'Values': ['DeleteOn']}]
        snapshot_remove = ec2.describe_snapshots(OwnerIds=account_id, Filters=filter)

        for snap in snapshot_remove['Snapshots']:
            snap_create_date = str(snap['StartTime'])
            snap_create_date = datetime.datetime.strptime(snap_create_date, '%Y-%m-%d %H:%M:%S+00:00').date()
            for tags in snap['Tags']:
                if tags["Key"] == 'DeleteOn':
                    snap_delete_date = str(tags["Value"])
                    snap_delete_date = datetime.datetime.strptime(snap_delete_date, '%Y-%m-%d').date()
            if snap_delete_date < snap_create_date:
                print "INFO: Deleting snapshot %s " % (snap['SnapshotId'])
                ec2.delete_snapshot(SnapshotId=snap['SnapshotId'])
