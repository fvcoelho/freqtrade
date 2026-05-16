import{$ as e,E as t,Ht as n,L as r,P as i,R as a,_ as o,at as s,c,d as l,et as u,g as d,h as f,l as p,ot as m,r as h,s as g,u as _,ut as v,vt as y}from"./runtime-core.esm-bundler-DJInd-dt.js";import{s as b,t as x}from"./runtime-dom.esm-bundler-BFwWrC14.js";import{St as S,c as C,l as w,t as T}from"./button-9C91yk-3.js";import{E,O as D,n as O,o as k}from"./ftbotwrapper-BEGfQXdl.js";import{n as ee,r as te,t as A}from"./pairlistConfig-DGOOEREk.js";import{t as j}from"./message-hQhHq679.js";import{t as M}from"./TimeRangeSelect-5q5X6-_j.js";import{L as ne,P as N,U as P,V as F,z as I}from"./index-BpFhqtQV.js";import{t as L}from"./inputnumber-DluTdptk.js";import{t as R}from"./DraggableContainer-BP79AjfJ.js";import{t as z}from"./check-BJpf9DVp.js";import{t as B}from"./multiselect-C0h9vtbC.js";import{t as V}from"./ExchangeSelect-ClsEVbey.js";var H=w.extend({name:`progressbar`,style:`
    .p-progressbar {
        display: block;
        position: relative;
        overflow: hidden;
        height: dt('progressbar.height');
        background: dt('progressbar.background');
        border-radius: dt('progressbar.border.radius');
    }

    .p-progressbar-value {
        margin: 0;
        background: dt('progressbar.value.background');
    }

    .p-progressbar-label {
        color: dt('progressbar.label.color');
        font-size: dt('progressbar.label.font.size');
        font-weight: dt('progressbar.label.font.weight');
    }

    .p-progressbar-determinate .p-progressbar-value {
        height: 100%;
        width: 0%;
        position: absolute;
        display: none;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        transition: width 1s ease-in-out;
    }

    .p-progressbar-determinate .p-progressbar-label {
        display: inline-flex;
    }

    .p-progressbar-indeterminate .p-progressbar-value::before {
        content: '';
        position: absolute;
        background: inherit;
        inset-block-start: 0;
        inset-inline-start: 0;
        inset-block-end: 0;
        will-change: inset-inline-start, inset-inline-end;
        animation: p-progressbar-indeterminate-anim 2.1s cubic-bezier(0.65, 0.815, 0.735, 0.395) infinite;
    }

    .p-progressbar-indeterminate .p-progressbar-value::after {
        content: '';
        position: absolute;
        background: inherit;
        inset-block-start: 0;
        inset-inline-start: 0;
        inset-block-end: 0;
        will-change: inset-inline-start, inset-inline-end;
        animation: p-progressbar-indeterminate-anim-short 2.1s cubic-bezier(0.165, 0.84, 0.44, 1) infinite;
        animation-delay: 1.15s;
    }

    @keyframes p-progressbar-indeterminate-anim {
        0% {
            inset-inline-start: -35%;
            inset-inline-end: 100%;
        }
        60% {
            inset-inline-start: 100%;
            inset-inline-end: -90%;
        }
        100% {
            inset-inline-start: 100%;
            inset-inline-end: -90%;
        }
    }
    @-webkit-keyframes p-progressbar-indeterminate-anim {
        0% {
            inset-inline-start: -35%;
            inset-inline-end: 100%;
        }
        60% {
            inset-inline-start: 100%;
            inset-inline-end: -90%;
        }
        100% {
            inset-inline-start: 100%;
            inset-inline-end: -90%;
        }
    }

    @keyframes p-progressbar-indeterminate-anim-short {
        0% {
            inset-inline-start: -200%;
            inset-inline-end: 100%;
        }
        60% {
            inset-inline-start: 107%;
            inset-inline-end: -8%;
        }
        100% {
            inset-inline-start: 107%;
            inset-inline-end: -8%;
        }
    }
    @-webkit-keyframes p-progressbar-indeterminate-anim-short {
        0% {
            inset-inline-start: -200%;
            inset-inline-end: 100%;
        }
        60% {
            inset-inline-start: 107%;
            inset-inline-end: -8%;
        }
        100% {
            inset-inline-start: 107%;
            inset-inline-end: -8%;
        }
    }
`,classes:{root:function(e){var t=e.instance;return[`p-progressbar p-component`,{"p-progressbar-determinate":t.determinate,"p-progressbar-indeterminate":t.indeterminate}]},value:`p-progressbar-value`,label:`p-progressbar-label`}}),U={name:`ProgressBar`,extends:{name:`BaseProgressBar`,extends:C,props:{value:{type:Number,default:null},mode:{type:String,default:`determinate`},showValue:{type:Boolean,default:!0}},style:H,provide:function(){return{$pcProgressBar:this,$parentInstance:this}}},inheritAttrs:!1,computed:{progressStyle:function(){return{width:this.value+`%`,display:`flex`}},indeterminate:function(){return this.mode===`indeterminate`},determinate:function(){return this.mode===`determinate`},dataP:function(){return S({determinate:this.determinate,indeterminate:this.indeterminate})}}},W=[`aria-valuenow`,`data-p`],G=[`data-p`],K=[`data-p`],q=[`data-p`];function J(e,r,o,s,c,u){return i(),l(`div`,t({role:`progressbar`,class:e.cx(`root`),"aria-valuemin":`0`,"aria-valuenow":e.value,"aria-valuemax":`100`,"data-p":u.dataP},e.ptmi(`root`)),[u.determinate?(i(),l(`div`,t({key:0,class:e.cx(`value`),style:u.progressStyle,"data-p":u.dataP},e.ptm(`value`)),[e.value!=null&&e.value!==0&&e.showValue?(i(),l(`div`,t({key:0,class:e.cx(`label`),"data-p":u.dataP},e.ptm(`label`)),[a(e.$slots,`default`,{},function(){return[f(n(e.value+`%`),1)]})],16,K)):_(``,!0)],16,G)):u.indeterminate?(i(),l(`div`,t({key:1,class:e.cx(`value`),"data-p":u.dataP},e.ptm(`value`)),null,16,q)):_(``,!0)],16,W)}U.render=J;var Y={viewBox:`0 0 24 24`,width:`1.2em`,height:`1.2em`};function X(e,t){return i(),l(`svg`,Y,[...t[0]||=[c(`path`,{fill:`currentColor`,d:`M8 17v-2h8v2zm8-7l-4 4l-4-4h2.5V7h3v3zM5 3h14a2 2 0 0 1 2 2v14c0 1.11-.89 2-2 2H5a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2m0 2v14h14V5z`},null,-1)]])}var Z=m({name:`mdi-download-box-outline`,render:X}),Q={class:`flex flex-row items-end gap-1`},re={class:`ms-2 w-full grow space-y-1`},ie=[`title`],ae={key:1},oe={class:`flex justify-between`},se={key:1},ce={key:2,class:`w-25`},le={key:3,class:`flex flex-col md:flex-row w-full grow gap-2`},ue=o({__name:`BackgroundJobTracking`,setup(t){let{runningJobs:a,clearJobs:o}=k();return(t,s)=>{let u=Z,m=z,g=U,v=N,b=T;return i(),l(`div`,Q,[c(`ul`,re,[(i(!0),l(h,null,r(y(a),(e,t)=>(i(),l(`li`,{key:t,class:`border p-1 pb-2 rounded-sm dark:border-surface-700 border-surface-300 flex gap-2 items-center`,title:t},[e.taskStatus?.job_category===`download_data`?(i(),p(u,{key:0})):(i(),l(`span`,ae,n(e.taskStatus?.job_category),1)),c(`div`,oe,[e.taskStatus?.status===`success`?(i(),p(m,{key:0,class:`text-success`,title:``})):(i(),l(`span`,se,n(e.taskStatus?.status),1)),e.taskStatus?.progress?(i(),l(`span`,ce,n(e.taskStatus?.progress),1)):_(``,!0)]),e.taskStatus?.progress?(i(),p(g,{key:2,class:`w-full grow`,value:e.taskStatus?.progress/100*100,"show-progress":``,max:100,striped:``},null,8,[`value`])):_(``,!0),e.taskStatus?.progress_tasks?(i(),l(`div`,le,[(i(!0),l(h,null,r(Object.entries(e.taskStatus?.progress_tasks),([t,r])=>(i(),l(`div`,{key:t,class:`w-full`},[f(n(r.description)+` `,1),d(g,{class:`w-full grow`,value:Math.round(r.progress/r.total*100*100)/100,"show-progress":``,pt:{value:{class:e.taskStatus.status===`success`?`bg-emerald-500`:`bg-amber-500`}},striped:``},null,8,[`value`,`pt`])]))),128))])):_(``,!0)],8,ie))),128))]),Object.keys(y(a)).length>0?(i(),p(b,{key:0,severity:`secondary`,class:`ms-auto`,onClick:y(o)},{icon:e(()=>[d(v)]),_:1},8,[`onClick`])):_(``,!0)])}}}),de=v([{description:`All USDT Pairs`,pairs:[`.*/USDT`]},{description:`All USDT Futures Pairs`,pairs:[`.*/USDT:USDT`]}]);function fe(){return{pairTemplates:g(()=>de.value.map((e,t)=>({...e,idx:t})))}}var pe={class:`px-1 mx-auto w-full max-w-4xl lg:max-w-7xl`},me={class:`flex mb-3 gap-3 flex-col`},he={class:`flex flex-col gap-3`},ge={class:`flex flex-col lg:flex-row gap-3`},_e={class:`flex-fill`},ve={class:`flex flex-col gap-2`},ye={class:`flex gap-2`},be={class:`flex flex-col gap-1`},xe={class:`flex flex-col gap-1`},Se={class:`flex-fill px-3`},Ce={class:`flex flex-col gap-2`},we={class:`px-3 border dark:border-surface-700 border-surface-300 p-2 rounded-sm`},$={class:`flex flex-col gap-2`},Te={class:`flex justify-between items-center`},Ee={key:0},De={key:1,class:`flex items-center gap-2`},Oe={class:`mb-2 border dark:border-surface-700 border-surface-300 rounded-sm p-2 text-start`},ke={class:`mb-2 border dark:border-surface-700 border-surface-300 rounded-md p-2 text-start`},Ae={class:`grid grid-cols md:grid-cols-2 items-center gap-2`},je={class:`mb-2 border dark:border-surface-700 border-surface-300 rounded-md p-2 text-start`},Me={class:`px-3`},Ne=o({__name:`DownloadDataMain`,setup(t){let a=O(),o=A(),m=v([`BTC/USDT`,`ETH/USDT`,``]),g=v([`5m`,`1h`]),S=v({useCustomTimerange:!1,timerange:``,days:30}),{pairTemplates:C}=fe(),w=v({customExchange:!1,selectedExchange:{exchange:`binance`,trade_mode:{margin_mode:E.NONE,trading_mode:D.SPOT}}}),k=v({erase:!1,prepend_data:!1,downloadTrades:!1,candleTypes:[]}),N=v(!1),P=[{text:`Spot`,value:`spot`},{text:`Futures`,value:`futures`},{text:`Funding Rate`,value:`funding_rate`},{text:`Mark`,value:`mark`},{text:`Index`,value:`index`},{text:`Premium Index`,value:`premiumIndex`}];function z(e){m.value.push(...e)}function H(e){m.value=[...e]}async function U(){let e={pairs:m.value.filter(e=>e!==``),timeframes:g.value.filter(e=>e!==``)};S.value.useCustomTimerange&&S.value.timerange?e.timerange=S.value.timerange:e.days=S.value.days,N.value&&(e.erase=k.value.erase,e.download_trades=k.value.downloadTrades,w.value.customExchange&&(e.exchange=w.value.selectedExchange.exchange,e.trading_mode=w.value.selectedExchange.trade_mode.trading_mode,e.margin_mode=w.value.selectedExchange.trade_mode.margin_mode),a.activeBot.botFeatures.downloadDataCandleTypes&&k.value.candleTypes.length>0&&(e.candle_types=k.value.candleTypes),a.activeBot.botFeatures.downloadDataPrepend&&k.value.prepend_data&&(e.prepend_data=!0)),await a.activeBot.startDataDownload(e)}return(t,v)=>{let E=ue,D=ee,O=T,A=F,W=I,G=M,K=L,q=ne,J=te,Y=j,X=B,Z=V,Q=R;return i(),l(`div`,pe,[d(E,{class:`mb-4`}),d(Q,{header:`Downloading Data`,class:`mx-1 p-4`},{default:e(()=>[c(`div`,me,[c(`div`,he,[c(`div`,ge,[c(`div`,_e,[c(`div`,ve,[v[14]||=c(`div`,{class:`flex justify-between`},[c(`h4`,{class:`text-start font-bold text-lg`},`Select Pairs`),c(`h5`,{class:`text-start font-bold text-lg`},`Pairs from template`)],-1),c(`div`,ye,[d(D,{modelValue:y(m),"onUpdate:modelValue":v[0]||=e=>s(m)?m.value=e:null,placeholder:`Pair`,size:`small`,class:`grow`},null,8,[`modelValue`]),c(`div`,be,[c(`div`,xe,[(i(!0),l(h,null,r(y(C),t=>(i(),p(O,{key:t.idx,severity:`secondary`,title:t.pairs.reduce((e,t)=>`${e}${t}\n`,``),onClick:e=>z(t.pairs)},{default:e(()=>[f(n(t.description),1)]),_:2},1032,[`title`,`onClick`]))),128))]),d(A),d(O,{disabled:y(o).whitelist.length===0,title:`Add all pairs from Pairlist Config - requires the pairlist config to have ran first.`,severity:`secondary`,onClick:v[1]||=e=>H(y(o).whitelist)},{default:e(()=>[...v[13]||=[f(` Use Pairs from Pairlist Config `,-1)]]),_:1},8,[`disabled`])])])])]),c(`div`,Se,[c(`div`,Ce,[v[15]||=c(`h4`,{class:`text-start font-bold text-lg`},`Select timeframes`,-1),d(D,{modelValue:y(g),"onUpdate:modelValue":v[2]||=e=>s(g)?g.value=e:null,placeholder:`Timeframe`},null,8,[`modelValue`])])])]),c(`div`,we,[c(`div`,$,[c(`div`,Te,[v[17]||=c(`h4`,{class:`text-start mb-0 font-bold text-lg`},`Time Selection`,-1),d(W,{modelValue:y(S).useCustomTimerange,"onUpdate:modelValue":v[3]||=e=>y(S).useCustomTimerange=e,class:`mb-0`,switch:``},{default:e(()=>[...v[16]||=[f(` Use custom timerange `,-1)]]),_:1},8,[`modelValue`])]),y(S).useCustomTimerange?(i(),l(`div`,Ee,[d(G,{modelValue:y(S).timerange,"onUpdate:modelValue":v[4]||=e=>y(S).timerange=e},null,8,[`modelValue`])])):(i(),l(`div`,De,[v[18]||=c(`label`,null,`Days to download:`,-1),d(K,{modelValue:y(S).days,"onUpdate:modelValue":v[5]||=e=>y(S).days=e,type:`number`,"aria-label":`Days to download`,min:1,step:1,size:`small`},null,8,[`modelValue`])]))])]),c(`div`,Oe,[d(O,{class:`mb-2`,severity:`secondary`,onClick:v[6]||=e=>N.value=!y(N)},{default:e(()=>[v[19]||=f(` Advanced Options `,-1),y(N)?(i(),p(J,{key:1})):(i(),p(q,{key:0}))]),_:1}),d(x,null,{default:e(()=>[u(c(`div`,null,[d(Y,{severity:`info`,class:`mb-2 py-2`},{default:e(()=>[...v[20]||=[f(` Advanced options (Erase data, Download trades, and Custom Exchange settings) will only be applied when this section is expanded. `,-1)]]),_:1}),c(`div`,ke,[d(W,{modelValue:y(k).erase,"onUpdate:modelValue":v[7]||=e=>y(k).erase=e,class:`mb-2`},{default:e(()=>[...v[21]||=[f(`Erase existing data`,-1)]]),_:1},8,[`modelValue`]),y(a).activeBot.botFeatures.downloadDataPrepend?(i(),p(W,{key:0,modelValue:y(k).prepend_data,"onUpdate:modelValue":v[8]||=e=>y(k).prepend_data=e,class:`mb-2`},{default:e(()=>[...v[22]||=[f(`Prepend data when downloading`,-1)]]),_:1},8,[`modelValue`])):_(``,!0),d(W,{modelValue:y(k).downloadTrades,"onUpdate:modelValue":v[9]||=e=>y(k).downloadTrades=e,class:`mb-2`},{default:e(()=>[...v[23]||=[f(` Download Trades instead of OHLCV data `,-1)]]),_:1},8,[`modelValue`]),c(`div`,Ae,[y(a).activeBot.botFeatures.downloadDataCandleTypes?(i(),p(X,{key:0,modelValue:y(k).candleTypes,"onUpdate:modelValue":v[10]||=e=>y(k).candleTypes=e,options:P,"option-label":`text`,"option-value":`value`,placeholder:`Select Candle Types`},null,8,[`modelValue`])):_(``,!0),v[24]||=c(`small`,null,`When no candle-type is selected, freqtrade will download the necessary candle types for regular operation automatically.`,-1)])]),c(`div`,je,[d(W,{modelValue:y(w).customExchange,"onUpdate:modelValue":v[11]||=e=>y(w).customExchange=e,class:`mb-2`},{default:e(()=>[...v[25]||=[f(` Custom Exchange `,-1)]]),_:1},8,[`modelValue`]),d(x,{name:`fade`},{default:e(()=>[u(d(Z,{modelValue:y(w).selectedExchange,"onUpdate:modelValue":v[12]||=e=>y(w).selectedExchange=e},null,8,[`modelValue`]),[[b,y(w).customExchange]])]),_:1})])],512),[[b,y(N)]])]),_:1})]),c(`div`,Me,[d(O,{severity:`primary`,onClick:U},{default:e(()=>[...v[26]||=[f(`Start Download`,-1)]]),_:1})])])])]),_:1})])}}}),Pe={};function Fe(e,t){let n=Ne;return i(),p(n,{class:`pt-4`})}var Ie=P(Pe,[[`render`,Fe]]);export{Ie as default};
//# sourceMappingURL=DownloadDataView-BZNg_6aG.js.map