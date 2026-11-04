import {brand} from './brand.mjs';
export const shots=[
  {id:'hook',start:0,end:3,label:'BANC FAT LOCAL',title:brand.hook,asset:'pid',subtitle:'Un banc local pour préparer vos essais PLC.',move:'hero'},
  {id:'pid',start:3,end:7,label:'P&ID',title:'Agissez sur le procédé.',asset:'pid',subtitle:'Commandes, retours et niveaux se lisent sur le P&ID.',move:'pan'},
  {id:'bool',start:7,end:10,label:'ENTRÉES BOOL',title:'Déclenchez une impulsion.',asset:'bool',subtitle:'Une impulsion de 300 ms, ou un maintien explicite.',move:'push'},
  {id:'analog',start:10,end:14,label:'STIMULUS ANALOGIQUE',title:'Préparez la valeur à écrire.',asset:'analog',subtitle:'12 mA correspondent ici à 13 824 points et 50 %.',move:'macro'},
  {id:'timed',start:14,end:18,label:'SCÉNARIO TEMPORISÉ',title:'Rejouez le même essai.',asset:'timed',subtitle:'Les attentes restent distinctes du verdict humain.',move:'slide'},
  {id:'guided',start:18,end:23,label:'FAT PAS À PAS',title:'Préparez chaque STEP.',asset:'guided',subtitle:'Écritures groupées, résultat attendu, observation à saisir.',move:'guided'},
  {id:'trends',start:23,end:27,label:'TENDANCES',title:'Suivez les valeurs échangées.',asset:'trends',subtitle:'Retrouvez les courbes, les valeurs et leur qualité.',move:'panReverse'},
  {id:'report',start:27,end:31,label:'RAPPORT ET TRACES',title:'Conservez la preuve de l’essai.',asset:'report',subtitle:'Exportez le rapport, les traces CSV et le détail JSON.',move:'paper'},
  {id:'archive',start:31,end:34,label:'PROJETS ET ARCHIVES',title:'Gardez l’historique.',asset:'archive',subtitle:'L’archive restaure le projet dans un nouveau dossier.',move:'slide'},
  {id:'ai',start:34,end:37,label:'CLIENT IA EXTERNE',title:'Pilotez l’API locale.',asset:'cli',subtitle:'Votre IA pilote le banc par l’API locale.',move:'terminal'},
  {id:'proof',start:37,end:41,label:'CAMPAGNE RÉELLE ANTÉRIEURE',title:'Testé sur Siemens.',asset:null,subtitle:'31 attentes réussies sur TIA V21 et PLCSIM Advanced 8.',move:'proof'},
  {id:'signature',start:41,end:45,label:'VANGUARD SYSTEMS',title:brand.signature,asset:null,subtitle:'Version en préparation. vanguard-systems.ch',move:'signature'},
];
export const config={
  mode:'ads',exportName:'vanguard-fat-studio',brand,width:1080,height:1350,duration:45,fps:30,bpm:128,
  colors:{background:'#EFF4FB',floor:'#FFFFFF',ink:'#101318',muted:'#5B6678',blue:'#0055DD',blueDeep:'#0048BC',border:'#D5E0F2'},
  assets:{logo:brand.logo,logoWhite:brand.logoWhite},services:[],events:{pid:3,bool:7,analog:10,timed:14,guided:18,trends:23,report:27,archive:31,ai:34,proof:37,signature:41},shots,
  audio:{accents:[{time:.08,type:'impact'},{time:3,type:'transition'},{time:7,type:'tick'},
    {time:10,type:'impact'},{time:14,type:'transition'},{time:18,type:'impact'},
    {time:23,type:'whoosh'},{time:27,type:'tick'},{time:31,type:'transition'},
    {time:34,type:'impact'},{time:37,type:'rise'},{time:41,type:'resolve'}]},
  reviewTimes:[.2,1.8,3.2,5.2,7.2,8.8,10.2,12.8,14.2,16.8,18.2,21.3,23.2,25.4,27.3,29.3,31.3,33.3,34.3,36.4,37.3,39.6,41.3,43.7,44.95],
};
