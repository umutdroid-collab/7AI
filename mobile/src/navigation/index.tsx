import React from "react";
import { ActivityIndicator, View } from "react-native";
import { NavigationContainer, DarkTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useAuth } from "../context/AuthContext";
import { colors, typography } from "../theme";
import HeaderProfileButton from "../components/HeaderProfileButton";
import Icon, { IconName } from "../components/Icon";

import LoginScreen from "../screens/auth/LoginScreen";
import StockListScreen from "../screens/stock/StockListScreen";
import StockDetailScreen from "../screens/stock/StockDetailScreen";
import TransferStockScreen from "../screens/stock/TransferStockScreen";
import AddStockScreen from "../screens/stock/AddStockScreen";
import AddHospitalScreen from "../screens/stock/AddHospitalScreen";
import HospitalListScreen from "../screens/stock/HospitalListScreen";
import AddProductScreen from "../screens/stock/AddProductScreen";
import ProductListScreen from "../screens/stock/ProductListScreen";
import InvoiceListScreen from "../screens/invoices/InvoiceListScreen";
import InvoiceDetailScreen from "../screens/invoices/InvoiceDetailScreen";
import NotificationsScreen from "../screens/invoices/NotificationsScreen";
import AssistantChatScreen from "../screens/assistant/AssistantChatScreen";
import CheckInScreen from "../screens/checkins/CheckInScreen";
import ProfileScreen from "../screens/profile/ProfileScreen";
import BulkUploadScreen from "../screens/profile/BulkUploadScreen";
import BackupsScreen from "../screens/profile/BackupsScreen";
import AuditLogScreen from "../screens/profile/AuditLogScreen";
import FollowUpsScreen from "../screens/profile/FollowUpsScreen";
import DashboardScreen from "../screens/profile/DashboardScreen";
import ClinicalDocumentsScreen from "../screens/assistant/ClinicalDocumentsScreen";
import PersonelTakipScreen from "../screens/targets/PersonelTakipScreen";
import AddSalesTargetScreen from "../screens/targets/AddSalesTargetScreen";

const StockStackNav = createNativeStackNavigator();
const InvoiceStackNav = createNativeStackNavigator();
const AssistantStackNav = createNativeStackNavigator();
const CheckInStackNav = createNativeStackNavigator();
const TargetsStackNav = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const screenOptions = {
  headerStyle: { backgroundColor: colors.surface },
  headerTintColor: colors.text,
  contentStyle: { backgroundColor: colors.background },
};

function StockStack() {
  return (
    <StockStackNav.Navigator screenOptions={screenOptions}>
      <StockStackNav.Screen
        name="StockList"
        component={StockListScreen}
        options={({ navigation }) => ({ title: "Stok Takip", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <StockStackNav.Screen name="StockDetail" component={StockDetailScreen} options={{ title: "Ürün Detayı" }} />
      <StockStackNav.Screen name="TransferStock" component={TransferStockScreen} options={{ title: "Taşı" }} />
      <StockStackNav.Screen name="AddStock" component={AddStockScreen} options={{ title: "Yeni Stok Kaydı" }} />
      <StockStackNav.Screen name="AddHospital" component={AddHospitalScreen} options={{ title: "Yeni Hastane" }} />
      <StockStackNav.Screen name="HospitalList" component={HospitalListScreen} options={{ title: "Hastaneler" }} />
      <StockStackNav.Screen name="AddProduct" component={AddProductScreen} options={{ title: "Yeni Ürün" }} />
      <StockStackNav.Screen name="ProductList" component={ProductListScreen} options={{ title: "Ürünler" }} />
      <StockStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <StockStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
      <StockStackNav.Screen name="Backups" component={BackupsScreen} options={{ title: "Yedekler" }} />
      <StockStackNav.Screen name="AuditLog" component={AuditLogScreen} options={{ title: "İşlem Günlüğü" }} />
      <StockStackNav.Screen name="ClinicalDocuments" component={ClinicalDocumentsScreen} options={{ title: "Klinik Çalışmalar" }} />
      <StockStackNav.Screen name="FollowUps" component={FollowUpsScreen} options={{ title: "Hatırlatıcılar" }} />
      <StockStackNav.Screen name="Dashboard" component={DashboardScreen} options={{ title: "Pano" }} />
    </StockStackNav.Navigator>
  );
}

function InvoiceStack() {
  return (
    <InvoiceStackNav.Navigator screenOptions={screenOptions}>
      <InvoiceStackNav.Screen
        name="InvoiceList"
        component={InvoiceListScreen}
        options={({ navigation }) => ({ title: "Fatura Takip", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <InvoiceStackNav.Screen name="InvoiceDetail" component={InvoiceDetailScreen} options={{ title: "Fatura Detayı" }} />
      <InvoiceStackNav.Screen name="Notifications" component={NotificationsScreen} options={{ title: "Bildirimler" }} />
      <InvoiceStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <InvoiceStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
      <InvoiceStackNav.Screen name="Backups" component={BackupsScreen} options={{ title: "Yedekler" }} />
      <InvoiceStackNav.Screen name="AuditLog" component={AuditLogScreen} options={{ title: "İşlem Günlüğü" }} />
      <InvoiceStackNav.Screen name="ClinicalDocuments" component={ClinicalDocumentsScreen} options={{ title: "Klinik Çalışmalar" }} />
      <InvoiceStackNav.Screen name="FollowUps" component={FollowUpsScreen} options={{ title: "Hatırlatıcılar" }} />
    </InvoiceStackNav.Navigator>
  );
}

function AssistantStack() {
  return (
    <AssistantStackNav.Navigator screenOptions={screenOptions}>
      <AssistantStackNav.Screen
        name="AssistantChat"
        component={AssistantChatScreen}
        options={({ navigation }) => ({ title: "Klinik Asistan", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <AssistantStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <AssistantStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
      <AssistantStackNav.Screen name="Backups" component={BackupsScreen} options={{ title: "Yedekler" }} />
      <AssistantStackNav.Screen name="AuditLog" component={AuditLogScreen} options={{ title: "İşlem Günlüğü" }} />
      <AssistantStackNav.Screen name="ClinicalDocuments" component={ClinicalDocumentsScreen} options={{ title: "Klinik Çalışmalar" }} />
      <AssistantStackNav.Screen name="FollowUps" component={FollowUpsScreen} options={{ title: "Hatırlatıcılar" }} />
    </AssistantStackNav.Navigator>
  );
}

function CheckInStack() {
  return (
    <CheckInStackNav.Navigator screenOptions={screenOptions}>
      <CheckInStackNav.Screen
        name="CheckIn"
        component={CheckInScreen}
        options={({ navigation }) => ({ title: "Rapor", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <CheckInStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <CheckInStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
      <CheckInStackNav.Screen name="Backups" component={BackupsScreen} options={{ title: "Yedekler" }} />
      <CheckInStackNav.Screen name="AuditLog" component={AuditLogScreen} options={{ title: "İşlem Günlüğü" }} />
      <CheckInStackNav.Screen name="ClinicalDocuments" component={ClinicalDocumentsScreen} options={{ title: "Klinik Çalışmalar" }} />
      <CheckInStackNav.Screen name="FollowUps" component={FollowUpsScreen} options={{ title: "Hatırlatıcılar" }} />
    </CheckInStackNav.Navigator>
  );
}

function TargetsStack() {
  return (
    <TargetsStackNav.Navigator screenOptions={screenOptions}>
      <TargetsStackNav.Screen
        name="PersonelTakip"
        component={PersonelTakipScreen}
        options={({ navigation }) => ({ title: "Hedefler", headerRight: () => <HeaderProfileButton navigation={navigation} /> })}
      />
      <TargetsStackNav.Screen name="AddSalesTarget" component={AddSalesTargetScreen} options={{ title: "Yeni Hedef" }} />
      <TargetsStackNav.Screen name="Profile" component={ProfileScreen} options={{ title: "Profil" }} />
      <TargetsStackNav.Screen name="BulkUpload" component={BulkUploadScreen} options={{ title: "Toplu Ekleme" }} />
      <TargetsStackNav.Screen name="Backups" component={BackupsScreen} options={{ title: "Yedekler" }} />
      <TargetsStackNav.Screen name="AuditLog" component={AuditLogScreen} options={{ title: "İşlem Günlüğü" }} />
      <TargetsStackNav.Screen name="ClinicalDocuments" component={ClinicalDocumentsScreen} options={{ title: "Klinik Çalışmalar" }} />
      <TargetsStackNav.Screen name="FollowUps" component={FollowUpsScreen} options={{ title: "Hatırlatıcılar" }} />
    </TargetsStackNav.Navigator>
  );
}

const TABS: { name: string; label: string; icon: IconName; component: React.ComponentType<any> }[] = [
  { name: "Stok", label: "Stok Takip", icon: "stock", component: StockStack },
  { name: "Fatura", label: "Fatura Takip", icon: "invoice", component: InvoiceStack },
  { name: "Asistan", label: "Klinik Asistan", icon: "assistant", component: AssistantStack },
  { name: "Takip", label: "Rapor", icon: "location", component: CheckInStack },
  { name: "Personel", label: "Hedefler", icon: "targets", component: TargetsStack },
];

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          // Tasarımda sekme sırası 64px; güvenli alan payını React Navigation
          // kendisi ekliyor (iOS çentiği yüzünden sabit yükseklik verilmiyor).
          height: 64,
          paddingTop: 8,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textDim,
        tabBarLabelStyle: { ...typography.tabLabel, marginTop: 2 },
      }}
    >
      {TABS.map((tab) => (
        <Tab.Screen
          key={tab.name}
          name={tab.name}
          component={tab.component}
          options={{
            tabBarLabel: tab.label,
            tabBarIcon: ({ color }) => <Icon name={tab.icon} size={20} color={color} />,
          }}
        />
      ))}
    </Tab.Navigator>
  );
}

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    border: colors.border,
    primary: colors.primary,
    text: colors.text,
  },
};

export default function RootNavigator() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return <NavigationContainer theme={navTheme}>{user ? <MainTabs /> : <LoginScreen />}</NavigationContainer>;
}
