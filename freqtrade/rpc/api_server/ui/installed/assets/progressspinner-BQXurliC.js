import{$ as e,E as t,P as n,R as r,Rt as i,Z as a,_ as o,at as s,c,d as l,g as u,j as d,l as f,ot as p,r as m,u as h,ut as g,vt as _}from"./runtime-core.esm-bundler-DJInd-dt.js";import{l as v}from"./runtime-dom.esm-bundler-BFwWrC14.js";import{c as y,l as b,t as x}from"./button-9C91yk-3.js";import{n as S,t as C}from"./pencil-BQxgGnyb.js";import{t as w}from"./inputtext-bIt3AHux.js";import{P as T}from"./index-BpFhqtQV.js";import{t as E}from"./plus-box-outline-Ci6iGpby.js";import{t as D}from"./check-BJpf9DVp.js";var O={name:`InputGroup`,extends:{name:`BaseInputGroup`,extends:y,style:b.extend({name:`inputgroup`,style:`
    .p-inputgroup,
    .p-inputgroup .p-iconfield,
    .p-inputgroup .p-floatlabel,
    .p-inputgroup .p-iftalabel {
        display: flex;
        align-items: stretch;
        width: 100%;
    }

    .p-inputgroup .p-floatlabel .p-inputwrapper,
    .p-inputgroup .p-iftalabel .p-inputwrapper {
        display: inline-flex;
    }

    .p-inputgroup .p-inputtext,
    .p-inputgroup .p-inputwrapper {
        flex: 1 1 auto;
        width: 1%;
    }

    .p-inputgroupaddon {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: dt('inputgroup.addon.padding');
        background: dt('inputgroup.addon.background');
        color: dt('inputgroup.addon.color');
        border-block-start: 1px solid dt('inputgroup.addon.border.color');
        border-block-end: 1px solid dt('inputgroup.addon.border.color');
        min-width: dt('inputgroup.addon.min.width');
    }

    .p-inputgroupaddon:first-child,
    .p-inputgroupaddon + .p-inputgroupaddon {
        border-inline-start: 1px solid dt('inputgroup.addon.border.color');
    }

    .p-inputgroupaddon:last-child {
        border-inline-end: 1px solid dt('inputgroup.addon.border.color');
    }

    .p-inputgroupaddon:has(.p-button) {
        padding: 0;
        overflow: hidden;
    }

    .p-inputgroupaddon .p-button {
        border-radius: 0;
    }

    .p-inputgroup > .p-component,
    .p-inputgroup > .p-inputwrapper > .p-component,
    .p-inputgroup > .p-iconfield > .p-component,
    .p-inputgroup > .p-floatlabel > .p-component,
    .p-inputgroup > .p-floatlabel > .p-inputwrapper > .p-component,
    .p-inputgroup > .p-iftalabel > .p-component,
    .p-inputgroup > .p-iftalabel > .p-inputwrapper > .p-component {
        border-radius: 0;
        margin: 0;
    }

    .p-inputgroupaddon:first-child,
    .p-inputgroup > .p-component:first-child,
    .p-inputgroup > .p-inputwrapper:first-child > .p-component,
    .p-inputgroup > .p-iconfield:first-child > .p-component,
    .p-inputgroup > .p-floatlabel:first-child > .p-component,
    .p-inputgroup > .p-floatlabel:first-child > .p-inputwrapper > .p-component,
    .p-inputgroup > .p-iftalabel:first-child > .p-component,
    .p-inputgroup > .p-iftalabel:first-child > .p-inputwrapper > .p-component {
        border-start-start-radius: dt('inputgroup.addon.border.radius');
        border-end-start-radius: dt('inputgroup.addon.border.radius');
    }

    .p-inputgroupaddon:last-child,
    .p-inputgroup > .p-component:last-child,
    .p-inputgroup > .p-inputwrapper:last-child > .p-component,
    .p-inputgroup > .p-iconfield:last-child > .p-component,
    .p-inputgroup > .p-floatlabel:last-child > .p-component,
    .p-inputgroup > .p-floatlabel:last-child > .p-inputwrapper > .p-component,
    .p-inputgroup > .p-iftalabel:last-child > .p-component,
    .p-inputgroup > .p-iftalabel:last-child > .p-inputwrapper > .p-component {
        border-start-end-radius: dt('inputgroup.addon.border.radius');
        border-end-end-radius: dt('inputgroup.addon.border.radius');
    }

    .p-inputgroup .p-component:focus,
    .p-inputgroup .p-component.p-focus,
    .p-inputgroup .p-inputwrapper-focus,
    .p-inputgroup .p-component:focus ~ label,
    .p-inputgroup .p-component.p-focus ~ label,
    .p-inputgroup .p-inputwrapper-focus ~ label,
    .p-inputgroup .p-floatlabel .p-inputwrapper ~ label,
    .p-inputgroup .p-iftalabel .p-inputwrapper ~ label {
        z-index: 1;
    }

    .p-inputgroup > .p-button:not(.p-button-icon-only) {
        width: auto;
    }

    .p-inputgroup .p-iconfield + .p-iconfield .p-inputtext {
        border-inline-start: 0;
    }
`,classes:{root:`p-inputgroup`}}),provide:function(){return{$pcInputGroup:this,$parentInstance:this}}},inheritAttrs:!1};function k(e,i,a,o,s,c){return n(),l(`div`,t({class:e.cx(`root`)},e.ptmi(`root`)),[r(e.$slots,`default`)],16)}O.render=k;var A={name:`InputGroupAddon`,extends:{name:`BaseInputGroupAddon`,extends:y,style:b.extend({name:`inputgroupaddon`,classes:{root:`p-inputgroupaddon`}}),provide:function(){return{$pcInputGroupAddon:this,$parentInstance:this}}},inheritAttrs:!1};function j(e,i,a,o,s,c){return n(),l(`div`,t({class:e.cx(`root`)},e.ptmi(`root`)),[r(e.$slots,`default`)],16)}A.render=j;var M={viewBox:`0 0 24 24`,width:`1.2em`,height:`1.2em`};function N(e,t){return n(),l(`svg`,M,[...t[0]||=[c(`path`,{fill:`currentColor`,d:`M19 21H8V7h11m0-2H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2m-3-4H4a2 2 0 0 0-2 2v14h2V3h12z`},null,-1)]])}var P=p({name:`mdi-content-copy`,render:N}),F={class:`grow`},I=function(e){return e[e.None=0]=`None`,e[e.Editing=1]=`Editing`,e[e.Adding=2]=`Adding`,e[e.Duplicating=3]=`Duplicating`,e}(I||{}),L=o({__name:`EditValue`,props:{modelValue:{},allowEdit:{type:Boolean,default:!1},allowAdd:{type:Boolean,default:!1},allowDuplicate:{type:Boolean,default:!1},editableName:{},alignVertical:{type:Boolean,default:!1}},emits:[`delete`,`new`,`duplicate`,`rename`],setup(t,{emit:o}){let p=t,y=o,b=g(``),O=g(I.None);d(()=>{b.value=p.modelValue});function k(){O.value=I.None,b.value=p.modelValue}function A(){b.value+=` (copy)`,O.value=I.Duplicating}function j(){b.value=``,O.value=I.Adding}a(()=>p.modelValue,()=>{b.value=p.modelValue});function M(){O.value===I.Adding?y(`new`,b.value):O.value===I.Duplicating?y(`duplicate`,p.modelValue,b.value):y(`rename`,p.modelValue,b.value),O.value=I.None}return(a,o)=>{let d=w,p=C,g=x,y=P,N=T,L=E,R=D,z=S;return n(),l(`form`,{class:`flex flex-row`,onSubmit:v(M,[`prevent`])},[c(`div`,F,[_(O)===I.None?r(a.$slots,`default`,{key:0}):(n(),f(d,{key:1,modelValue:_(b),"onUpdate:modelValue":o[0]||=e=>s(b)?b.value=e:null,size:`small`,fluid:``},null,8,[`modelValue`]))]),c(`div`,{class:i([`mt-auto flex gap-1 ms-1`,t.alignVertical?`flex-col`:`flex-row`])},[t.allowEdit&&_(O)===I.None?(n(),l(m,{key:0},[u(g,{size:`small`,severity:`secondary`,title:`Edit this ${t.editableName}.`,onClick:o[1]||=e=>O.value=I.Editing},{icon:e(()=>[u(p)]),_:1},8,[`title`]),t.allowDuplicate?(n(),f(g,{key:0,size:`small`,severity:`secondary`,title:`Duplicate ${t.editableName}.`,onClick:A},{icon:e(()=>[u(y)]),_:1},8,[`title`])):h(``,!0),u(g,{size:`small`,severity:`secondary`,title:`Delete this ${t.editableName}.`,onClick:o[2]||=e=>a.$emit(`delete`,t.modelValue)},{icon:e(()=>[u(N)]),_:1},8,[`title`])],64)):h(``,!0),t.allowAdd&&_(O)===I.None?(n(),f(g,{key:1,size:`small`,title:`Add new ${t.editableName}.`,severity:`primary`,onClick:j},{icon:e(()=>[u(L)]),_:1},8,[`title`])):h(``,!0),_(O)===I.None?h(``,!0):(n(),l(m,{key:2},[u(g,{size:`small`,title:`Add new ${t.editableName}`,severity:`primary`,onClick:M},{icon:e(()=>[u(R)]),_:1},8,[`title`]),u(g,{size:`small`,title:`Abort`,severity:`secondary`,onClick:k},{icon:e(()=>[u(z)]),_:1})],64))],2)],32)}}}),R=b.extend({name:`progressspinner`,style:`
    .p-progressspinner {
        position: relative;
        margin: 0 auto;
        width: 100px;
        height: 100px;
        display: inline-block;
    }

    .p-progressspinner::before {
        content: '';
        display: block;
        padding-top: 100%;
    }

    .p-progressspinner-spin {
        height: 100%;
        transform-origin: center center;
        width: 100%;
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        right: 0;
        margin: auto;
        animation: p-progressspinner-rotate 2s linear infinite;
    }

    .p-progressspinner-circle {
        stroke-dasharray: 89, 200;
        stroke-dashoffset: 0;
        stroke: dt('progressspinner.colorOne');
        animation:
            p-progressspinner-dash 1.5s ease-in-out infinite,
            p-progressspinner-color 6s ease-in-out infinite;
        stroke-linecap: round;
    }

    @keyframes p-progressspinner-rotate {
        100% {
            transform: rotate(360deg);
        }
    }
    @keyframes p-progressspinner-dash {
        0% {
            stroke-dasharray: 1, 200;
            stroke-dashoffset: 0;
        }
        50% {
            stroke-dasharray: 89, 200;
            stroke-dashoffset: -35px;
        }
        100% {
            stroke-dasharray: 89, 200;
            stroke-dashoffset: -124px;
        }
    }
    @keyframes p-progressspinner-color {
        100%,
        0% {
            stroke: dt('progressspinner.color.one');
        }
        40% {
            stroke: dt('progressspinner.color.two');
        }
        66% {
            stroke: dt('progressspinner.color.three');
        }
        80%,
        90% {
            stroke: dt('progressspinner.color.four');
        }
    }
`,classes:{root:`p-progressspinner`,spin:`p-progressspinner-spin`,circle:`p-progressspinner-circle`}}),z={name:`ProgressSpinner`,extends:{name:`BaseProgressSpinner`,extends:y,props:{strokeWidth:{type:String,default:`2`},fill:{type:String,default:`none`},animationDuration:{type:String,default:`2s`}},style:R,provide:function(){return{$pcProgressSpinner:this,$parentInstance:this}}},inheritAttrs:!1,computed:{svgStyle:function(){return{"animation-duration":this.animationDuration}}}},B=[`fill`,`stroke-width`];function V(e,r,i,a,o,s){return n(),l(`div`,t({class:e.cx(`root`),role:`progressbar`},e.ptmi(`root`)),[(n(),l(`svg`,t({class:e.cx(`spin`),viewBox:`25 25 50 50`,style:s.svgStyle},e.ptm(`spin`)),[c(`circle`,t({class:e.cx(`circle`),cx:`50`,cy:`50`,r:`20`,fill:e.fill,"stroke-width":e.strokeWidth,strokeMiterlimit:`10`},e.ptm(`circle`)),null,16,B)],16))],16)}z.render=V;export{O as a,A as i,L as n,P as r,z as t};
//# sourceMappingURL=progressspinner-BQXurliC.js.map