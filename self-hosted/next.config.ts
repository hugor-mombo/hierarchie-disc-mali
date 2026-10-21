import type {NextConfig} from 'next';
const config:NextConfig={output:'standalone',outputFileTracingRoot:process.cwd(),poweredByHeader:false,serverExternalPackages:['pg','cht-conf']};
export default config;
