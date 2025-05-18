# Service d'analyse humidite du jardin avec recommendation d'arrosage automatique

Déployer l'application en utilisant la fonctionnalité Source To Image. 
Peut être fait en 2 clics via la console Developer de OpenShift. Add from Git. 

Peut être déployé via la commande oc new-app
```
oc new-app https://github.com/marouim/jardin-ai.git
```

Créer les configmap et secret pour la sonde. Ils sont également partagé avec le service jardin-ai. Seul 

ConfigMap
```
apiVersion: v1
kind: ConfigMap
metadata:
  name: jardin-ai-config
data:
  SONDE_IP: "1.1.1.1"
  VALEUR_SEC: "835"
  VALEUR_HUMIDE: "420"
  SEUIL_ARROSAGE: "30"
  LAT: "latitude"
  LON: "longitude"
  PORT: "8080"
```

Secret
```
apiVersion: v1
kind: Secret
metadata:
  name: jardin-ai-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: YourKey
  WEATHER_API_KEY: YourKey
```

Attach Config and Secret to the deployment
```
template:
    spec:
      containers:
        - name: jardin-ai-metrics-git
          envFrom:
            - configMapRef:
                name: jardin-ai-config
            - secretRef:
                name: jardin-ai-secrets
```

Permettre la compilation automatique via WebHook dans GitHub

```
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  annotations:
    rbac.authorization.kubernetes.io/autoupdate: "true"
  name: webhook-access-unauthenticated
  namespace: jardin-ai
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: "system:webhook"
subjects:
  - apiGroup: rbac.authorization.k8s.io
    kind: Group
    name: "system:unauthenticated"
```
