"""
US 2.1 : Configuration d'Amazon OpenSearch Serverless (mode Classic)
Crée :
  - Une collection OpenSearch Serverless de type VECTORSEARCH
  - Les security policies requises (encryption, network, data access)
  - Un index k-NN avec la dimensionnalité correspondant à Titan Embeddings V2 (1024)

Pour libérer les coûts entre les sessions de travail :
    cdk destroy   (supprime la collection, arrête la facturation)
    cdk deploy    (la recrée en 1-2 minutes)
Les données restent en sécurité dans S3 (dossier embeddings/) entre les deux.
"""

from aws_cdk import Stack, CfnOutput
from constructs import Construct
from aws_cdk import aws_opensearchserverless as opensearchserverless
from aws_cdk import aws_ssm as ssm

# --- Configuration ---
COLLECTION_NAME = "smartovate-rag-collection"
INDEX_NAME = "rag-chunks-index"
EMBEDDING_DIMENSION = 1024  # Titan Embeddings V2

# ARN de l'utilisateur IAM qui doit pouvoir écrire/lire dans la collection
# (celui utilisé par vos scripts Python locaux)
BACKEND_USER_ARN = "arn:aws:iam::136609826386:user/rag-backend-mariem"

# ARN du rôle technique utilisé par CDK/CloudFormation pour déployer
# (nécessaire car c'est LUI qui exécute concrètement la création de l'index, pas l'utilisateur)
CDK_EXEC_ROLE_ARN = "arn:aws:iam::136609826386:role/cdk-hnb659fds-cfn-exec-role-136609826386-eu-north-1"
APP_RUNNER_INSTANCE_ROLE_ARN = "arn:aws:iam::136609826386:role/AppRunnerInstanceRole"
ECS_TASK_ROLE_ARN = "arn:aws:iam::136609826386:role/smartovate-rag-task-role"


class InfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- 1. Politique de chiffrement (obligatoire, doit exister avant la collection) ---
        encryption_policy = opensearchserverless.CfnSecurityPolicy(
            self, "EncryptionPolicy",
            name="smartovate-rag-encryption-policy",
            type="encryption",
            policy=f'{{"Rules":[{{"ResourceType":"collection","Resource":["collection/{COLLECTION_NAME}"]}}],"AWSOwnedKey":true}}',
        )

        # --- 2. Politique réseau (accès public simplifié pour ce PoC de dev) ---
        network_policy = opensearchserverless.CfnSecurityPolicy(
            self, "NetworkPolicy",
            name="smartovate-rag-network-policy",
            type="network",
            policy=f'[{{"Rules":[{{"ResourceType":"collection","Resource":["collection/{COLLECTION_NAME}"]}},{{"ResourceType":"dashboard","Resource":["collection/{COLLECTION_NAME}"]}}],"AllowFromPublic":true}}]',
        )

        # --- 3. La collection elle-même ---
        collection = opensearchserverless.CfnCollection(
            self, "RagCollection",
            name=COLLECTION_NAME,
            type="VECTORSEARCH",
            description="Collection vectorielle pour le systeme RAG Smartovate",
        )
        collection.add_dependency(encryption_policy)
        collection.add_dependency(network_policy)

        # --- 4. Politique d'accès aux données : autorise rag-backend-mariem à lire/écrire ---
        data_access_policy = opensearchserverless.CfnAccessPolicy(
            self, "DataAccessPolicy",
            name="smartovate-rag-access-policy",
            type="data",
            policy=(
                f'[{{"Rules":[{{"ResourceType":"collection","Resource":["collection/{COLLECTION_NAME}"],'
                f'"Permission":["aoss:*"]}},{{"ResourceType":"index","Resource":["index/{COLLECTION_NAME}/*"],'
                f'"Permission":["aoss:*"]}}],"Principal":["{BACKEND_USER_ARN}","{CDK_EXEC_ROLE_ARN}","{APP_RUNNER_INSTANCE_ROLE_ARN}","{ECS_TASK_ROLE_ARN}"]}}]'
            ),
        )
        data_access_policy.add_dependency(collection)

        # --- 5. L'index k-NN pour stocker les chunks + embeddings ---
        index = opensearchserverless.CfnIndex(
            self, "RagIndex",
            collection_endpoint=collection.attr_collection_endpoint,
            index_name=INDEX_NAME,
            settings=opensearchserverless.CfnIndex.IndexSettingsProperty(
                index=opensearchserverless.CfnIndex.IndexProperty(
                    knn=True,
                )
            ),
            mappings=opensearchserverless.CfnIndex.MappingsProperty(
                properties={
                    "embedding_vector": opensearchserverless.CfnIndex.PropertyMappingProperty(
                        type="knn_vector",
                        dimension=EMBEDDING_DIMENSION,
                        method=opensearchserverless.CfnIndex.MethodProperty(
                            name="hnsw",
                            engine="faiss",
                            space_type="cosinesimil",
                        ),
                    ),
                    "chunk_text": opensearchserverless.CfnIndex.PropertyMappingProperty(type="text"),
                    "source_document": opensearchserverless.CfnIndex.PropertyMappingProperty(type="keyword"),
                    "chunk_id": opensearchserverless.CfnIndex.PropertyMappingProperty(type="keyword"),
                }
            ),
        )
        index.add_dependency(data_access_policy)

        # --- 6. Paramètre SSM : rend l'endpoint accessible dynamiquement
        # aux scripts Python (local ou déployé sur ECS), sans valeur en dur ---
        endpoint_param = ssm.StringParameter(
            self, "OpenSearchEndpointParam",
            parameter_name="/smartovate-rag/opensearch-endpoint",
            string_value=collection.attr_collection_endpoint,
            description="Endpoint de la collection OpenSearch Serverless (mis à jour à chaque déploiement)",
        )
        endpoint_param.node.add_dependency(collection)


        # --- Sorties utiles (affichées après cdk deploy) ---
        CfnOutput(self, "CollectionEndpoint", value=collection.attr_collection_endpoint)
        CfnOutput(self, "CollectionArn", value=collection.attr_arn)
        CfnOutput(self, "IndexName", value=INDEX_NAME)