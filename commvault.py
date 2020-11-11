from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_route53 as route53,
    aws_ssm as ssm,
    aws_iam as iam,
    aws_s3 as s3,
    aws_efs as efs,
    aws_kms as kms
)
import os, yaml

class CommVaultStack(core.Stack):

    def __init__(self, scope: core.Construct, config: dict, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        if 'vpc_id' in config:
            vpc = ec2.Vpc.from_lookup(self, "ECS-VPC", vpc_id=config["vpc_id"])
        else:
            vpc = None
        cluster = ecs.Cluster(
            self, 
            cluster_name="commvault-cs",
            id="commvault",
            container_insights=True,
            vpc=vpc
        )

### Create demo bucket
        bucket = s3.Bucket(self,
        "commvault-bucket",
        bucket_name="commvault-demo-bucket-{}-{}".format(config["region"], config["account"])
        )
  
### This will allow the ALB to generate a certificate. 
        domain_zone = route53.HostedZone.from_lookup(self, "walkerzone", domain_name="code.awalker.dev")

### Create EFS
        # kms_key = kms.Key(self, "comm-vault-key")

        commvault_file_system = efs.FileSystem(self, 
            "comvault-efs",
            vpc=cluster.vpc,
            file_system_name="commvault-efs",
            encrypted=True,
            # kms_key=kms_key ,
        )
        # kms_key.grant_encrypt_decrypt(commvault_file_system.)



### Define Task Definition and add the container
        ecs_task = ecs.FargateTaskDefinition(
            self,
            "commvault-task"
        )

        ecs_task.add_container(
            "commvault-container",
            image=ecs.ContainerImage.from_registry("store/commvaultrepo/mediaagent:SP7"),
            essential=True,
            command=["-csclientname", "filesys", "-cshost", "-mountpath", '"/opt/libraryPath"', "-cvdport", "8600", "-clienthost", "-clientname", "dockermediaagent"],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="commvault"
            )
            
        ).add_port_mappings(
            ecs.PortMapping(
                container_port=80,
                host_port=80,
                protocol=ecs.Protocol.TCP
            )
        )
        
        ecs_task.add_to_task_role_policy(
            statement=iam.PolicyStatement(
                actions=["efs:*"],
                resources=['*'],
                effect=iam.Effect.ALLOW
            )
        )
### Create the ECS Service using the ApplicationLoadBalancedFargate pattern. 
        ecs_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, 
            "commvault-service",
            assign_public_ip=False,
            cluster=cluster,
            task_definition=ecs_task,
            protocol=elbv2.Protocol.HTTPS,
            redirect_http=True,
            domain_name="commvault.code.awalker.dev",
            domain_zone=domain_zone,
            platform_version=ecs.FargatePlatformVersion.VERSION1_4,
            public_load_balancer=False
        )

### Grant Read/Write to the s3 Bucket for the task
        bucket.grant_read_write(
            ecs_service.task_definition.task_role
        )



# -v $TMPDIR/CommvaultLogs:/var/log/commvault/Log_Files
        ecs_task.add_volume(
            name="CommvaultLogs",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=commvault_file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    #iam="ENABLED",
                    access_point_id=efs.AccessPoint(self, 
                        "CommvaultLog-access-point",
                        path="/CommvaultLogs",
                        file_system=commvault_file_system
                    ).access_point_id
                )
            )
        )
        ecs_task.default_container.add_mount_points(
            ecs.MountPoint(
                container_path="/var/log/commvault/Log_Files",
                source_volume="CommvaultLogs",
                read_only=False
            )
        )

# -v $TMPDIR/CommvaultRegistry/:/etc/CommVaultRegistry
        ecs_task.add_volume(
            name="CommVaultRegistry",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=commvault_file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    #iam="ENABLED",
                    access_point_id=efs.AccessPoint(self, 
                        "CommVaultRegistrys-access-point",
                        path="/CommVaultRegistry",
                        file_system=commvault_file_system
                    ).access_point_id
                )
            )
        )
        ecs_task.default_container.add_mount_points(
            ecs.MountPoint(
                container_path="/etc/CommVaultRegistry",
                source_volume="CommVaultRegistry",
                read_only=False
            )
        )

# -v $TMPDIR/libraryPath/:/opt/libraryPath
        ecs_task.add_volume(
            name="libraryPath",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=commvault_file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    #iam="ENABLED",
                    access_point_id=efs.AccessPoint(self, 
                        "libraryPath-access-point",
                        path="/libraryPath",
                        file_system=commvault_file_system
                    ).access_point_id
                )
            )
        )
        ecs_task.default_container.add_mount_points(
            ecs.MountPoint(
                container_path="/opt/libraryPath",
                source_volume="libraryPath",
                read_only=False
            )
        )

# -v $TMPDIR/IndexCache/:/opt/IndexCache
        ecs_task.add_volume(
            name="IndexCache",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=commvault_file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    #iam="ENABLED",
                    access_point_id=efs.AccessPoint(self, 
                        "IndexCache-access-point",
                        path="/IndexCache",
                        file_system=commvault_file_system
                    ).access_point_id
                )
            )
        )
        ecs_task.default_container.add_mount_points(
            ecs.MountPoint(
                container_path="/opt/IndexCache",
                source_volume="IndexCache",
                read_only=False
            )
        )

# -v $TMPDIR/jobResults/:/opt/jobResults
        ecs_task.add_volume(
            name="jobResults",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=commvault_file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    #iam="ENABLED",
                    access_point_id=efs.AccessPoint(self, 
                        "jobResults-access-point",
                        path="/jobResults",
                        file_system=commvault_file_system
                    ).access_point_id
                )
            )
        )
        ecs_task.default_container.add_mount_points(
            ecs.MountPoint(
                container_path="/opt/jobResults",
                source_volume="jobResults",
                read_only=False
            )
        )

# -v $TMPDIR/certificates:/opt/commvault/Base/certificates 
        ecs_task.add_volume(
            name="certificates",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=commvault_file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    #iam="ENABLED",
                    access_point_id=efs.AccessPoint(self, 
                        "certificates-access-point",
                        path="/certificates",
                        file_system=commvault_file_system
                    ).access_point_id
                )
            )
        )
        ecs_task.default_container.add_mount_points(
            ecs.MountPoint(
                container_path="/opt/commvault/Base/certificates",
                source_volume="certificates",
                read_only=False
            )
        )
    

app = core.App()
step = app.node.try_get_context("env")
config = yaml.load(open("env.yaml"), Loader=yaml.FullLoader)

env = core.Environment(region=config["region"], account=config["account"])
CommVaultStack(app, config, "commvault-demo", env=env)
app.synth()